#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <mutex>
#include <stdexcept>
#include <thread>

namespace {

int failures;

void expect(bool condition, const char* message) {
    if (condition) return;
    ++failures;
    printk("runtime-port: FAIL: %s\n", message);
}

void wait_for_release(std::atomic<int>& ready, std::atomic<bool>& release) {
    ready.fetch_add(1, std::memory_order_release);
    while (!release.load(std::memory_order_acquire)) k_msleep(1);
}

std::atomic<int> local_static_initializations{0};

int& concurrent_local_static() {
    static int value = [] {
        local_static_initializations.fetch_add(1, std::memory_order_relaxed);
        k_msleep(5);
        return 42;
    }();
    return value;
}

std::atomic<int> tls_destructor_count{0};
int tls_destructor_order[2] = {-1, -1};

struct ThreadLocalProbe {
    int id;
    ~ThreadLocalProbe() {
        const int index = tls_destructor_count.fetch_add(1, std::memory_order_relaxed);
        if (index < 2) tls_destructor_order[index] = id;
    }
};

void touch_thread_locals() {
    thread_local ThreadLocalProbe first{1};
    thread_local ThreadLocalProbe second{2};
    (void)first;
    (void)second;
}

std::atomic<int> unwind_destructors{0};
std::atomic<int> caught_exceptions{0};
std::atomic<int> zero_uncaught_after_catch{0};

struct UnwindProbe {
    ~UnwindProbe() {
        if (std::uncaught_exceptions() > 0)
            unwind_destructors.fetch_add(1, std::memory_order_relaxed);
    }
};

void throw_from_worker() {
    UnwindProbe probe;
    throw std::runtime_error("worker exception");
}

void test_concurrent_once_and_local_static() {
    constexpr int workers = 3;
    std::once_flag once;
    std::atomic<int> once_calls{0};
    std::atomic<int> ready{0};
    std::atomic<bool> release{false};
    std::atomic<int> static_ready{0};
    std::atomic<bool> static_release{false};
    std::atomic<int> static_values{0};

    auto work = [&] {
        wait_for_release(ready, release);
        std::call_once(once, [&] {
            once_calls.fetch_add(1, std::memory_order_relaxed);
            k_msleep(10);
        });
        wait_for_release(static_ready, static_release);
        if (concurrent_local_static() == 42)
            static_values.fetch_add(1, std::memory_order_relaxed);
    };

    std::thread first(work);
    std::thread second(work);
    std::thread third(work);
    while (ready.load(std::memory_order_acquire) != workers) k_msleep(1);
    release.store(true, std::memory_order_release);
    while (static_ready.load(std::memory_order_acquire) != workers) k_msleep(1);
    static_release.store(true, std::memory_order_release);
    first.join();
    second.join();
    third.join();

    expect(once_calls.load() == 1, "concurrent call_once executes once");
    expect(local_static_initializations.load() == 1,
           "function-local static initializes once");
    expect(static_values.load() == workers,
           "all workers observe the initialized local static");
}

void test_once_throw_and_retry() {
    std::once_flag once;
    std::atomic<int> attempts{0};
    bool first_threw = false;
    try {
        std::call_once(once, [&] {
            attempts.fetch_add(1, std::memory_order_relaxed);
            throw std::runtime_error("retry once");
        });
    } catch (const std::runtime_error&) {
        first_threw = true;
    }
    std::call_once(once, [&] { attempts.fetch_add(1, std::memory_order_relaxed); });
    std::call_once(once, [&] { attempts.fetch_add(1, std::memory_order_relaxed); });

    expect(first_threw, "call_once propagates initializer exceptions");
    expect(attempts.load() == 2, "call_once retries after a thrown initializer");
}

void test_condition_variable() {
    std::mutex mutex;
    std::condition_variable condition;
    bool ready = false;
    std::atomic<bool> waiter_entered{false};
    std::atomic<bool> woke{false};

    std::thread waiter([&] {
        std::unique_lock<std::mutex> lock(mutex);
        waiter_entered.store(true, std::memory_order_release);
        condition.wait(lock, [&] { return ready; });
        woke.store(true, std::memory_order_release);
    });
    while (!waiter_entered.load(std::memory_order_acquire)) k_msleep(1);
    {
        std::lock_guard<std::mutex> lock(mutex);
        ready = true;
    }
    condition.notify_one();
    waiter.join();
    expect(woke.load(std::memory_order_acquire),
           "condition_variable wakes a predicate waiter");
}

void test_exceptions_are_thread_local() {
    constexpr int workers = 2;
    std::atomic<int> ready{0};
    std::atomic<bool> release{false};
    auto work = [&] {
        wait_for_release(ready, release);
        try {
            throw_from_worker();
        } catch (const std::runtime_error&) {
            caught_exceptions.fetch_add(1, std::memory_order_relaxed);
            if (std::uncaught_exceptions() == 0)
                zero_uncaught_after_catch.fetch_add(1, std::memory_order_relaxed);
        }
    };

    std::thread first(work);
    std::thread second(work);
    while (ready.load(std::memory_order_acquire) != workers) k_msleep(1);
    release.store(true, std::memory_order_release);
    first.join();
    second.join();

    expect(caught_exceptions.load() == workers,
           "each worker catches its own exception");
    expect(unwind_destructors.load() == workers,
           "uncaught exception counts are maintained during unwinding");
    expect(zero_uncaught_after_catch.load() == workers,
           "uncaught exception counts clear after catch");
}

void test_thread_local_destructor_order() {
    std::thread worker(touch_thread_locals);
    worker.join();
    expect(tls_destructor_count.load() == 2,
           "thread-local destructors run before pthread exit completes");
    expect(tls_destructor_order[0] == 2 && tls_destructor_order[1] == 1,
           "thread-local destructors run in reverse initialization order");
}

void test_atomic64_contention_and_cas() {
    constexpr int workers = 3;
    constexpr int increments = 150;
    std::atomic<std::uint64_t> counter{0};
    std::atomic<int> ready{0};
    std::atomic<bool> release{false};
    auto work = [&] {
        wait_for_release(ready, release);
        for (int index = 0; index < increments; ++index) {
            std::uint64_t observed = counter.load(std::memory_order_relaxed);
            while (!counter.compare_exchange_weak(observed, observed + 1,
                                                  std::memory_order_relaxed,
                                                  std::memory_order_relaxed)) {
            }
        }
    };

    std::thread first(work);
    std::thread second(work);
    std::thread third(work);
    while (ready.load(std::memory_order_acquire) != workers) k_msleep(1);
    release.store(true, std::memory_order_release);
    first.join();
    second.join();
    third.join();

    expect(counter.load(std::memory_order_relaxed) == workers * increments,
           "64-bit compare-exchange increments do not lose updates");
    counter.store(7, std::memory_order_relaxed);
    std::uint64_t expected = 7;
    expect(counter.compare_exchange_strong(expected, 11, std::memory_order_relaxed),
           "64-bit compare-exchange succeeds for the expected value");
    expected = 7;
    expect(!counter.compare_exchange_strong(expected, 19, std::memory_order_relaxed) &&
               expected == 11,
           "64-bit compare-exchange updates expected after failure");
}

}  // namespace

int main() {
    printk("runtime-port: concurrent once/local static\n");
    test_concurrent_once_and_local_static();
    printk("runtime-port: once throw/retry\n");
    test_once_throw_and_retry();
    printk("runtime-port: condition variable\n");
    test_condition_variable();
    printk("runtime-port: exceptions\n");
    test_exceptions_are_thread_local();
    printk("runtime-port: TLS destructor order\n");
    test_thread_local_destructor_order();
    printk("runtime-port: atomic64 contention/CAS\n");
    test_atomic64_contention_and_cas();

    if (failures != 0) {
        printk("runtime-port: %d test(s) failed\n", failures);
        return 1;
    }
    printk("runtime-port: PASS\n");
    return 0;
}
