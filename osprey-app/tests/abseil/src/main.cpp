#include <absl/base/internal/low_level_alloc.h>
#include <absl/synchronization/mutex.h>
#include <absl/time/time.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include <array>
#include <cstddef>
#include <string>
#include <thread>

namespace {
constexpr int kThreads = 2;
constexpr int kIncrementsPerThread = 200;
absl::Mutex counter_mutex;
absl::CondVar condition;
int counter = 0;
bool notified = false;

size_t available_kernel_chunks() {
    void* chunks[256]{};
    size_t count = 0;
    while (count < std::size(chunks)) {
        void* p = k_malloc(128);
        if (p == nullptr) break;
        chunks[count++] = p;
    }
    for (size_t i = 0; i < count; ++i) k_free(chunks[i]);
    return count;
}

bool test_allocator_arenas() {
    auto* warm = absl::base_internal::LowLevelAlloc::NewArena(0);
    if (!absl::base_internal::LowLevelAlloc::DeleteArena(warm)) return false;
    const size_t before = available_kernel_chunks();
    for (int iteration = 0; iteration < 10; ++iteration) {
        auto* arena = absl::base_internal::LowLevelAlloc::NewArena(0);
        std::array<void*, 48> blocks{};
        for (size_t i = 0; i < blocks.size(); ++i) {
            blocks[i] = absl::base_internal::LowLevelAlloc::AllocWithArena(
                12 + ((i * 37 + iteration * 11) % 173), arena);
            if (blocks[i] == nullptr) return false;
        }
        for (size_t i = blocks.size(); i-- > 0;) {
            absl::base_internal::LowLevelAlloc::Free(blocks[i]);
        }
        if (!absl::base_internal::LowLevelAlloc::DeleteArena(arena)) return false;
    }
    return available_kernel_chunks() == before;
}

void increment_worker() {
    for (int i = 0; i < kIncrementsPerThread; ++i) {
        counter_mutex.Lock();
        ++counter;
        if (i < 3) k_msleep(1);
        counter_mutex.Unlock();
    }
}

bool test_mutex_and_condition_variable() {
    std::thread a(increment_worker);
    std::thread b(increment_worker);
    a.join();
    b.join();
    if (counter != kThreads * kIncrementsPerThread) return false;

    // Hold the mutex while starting the notifier. It cannot signal until
    // Wait atomically releases the mutex and enrolls this thread.
    counter_mutex.Lock();
    std::thread notifier([] {
        counter_mutex.Lock();
        notified = true;
        condition.Signal();
        counter_mutex.Unlock();
    });
    while (!notified) condition.Wait(&counter_mutex);
    counter_mutex.Unlock();
    notifier.join();
    return notified;
}

bool test_time_formatting() {
    const absl::Time instant = absl::FromUnixSeconds(1700000000);
    absl::TimeZone utc;
    absl::TimeZone new_york;
    const bool utc_loaded = absl::LoadTimeZone("UTC", &utc);
    const bool new_york_rejected = !absl::LoadTimeZone("America/New_York", &new_york);
    const std::string utc_text = absl::FormatTime("%Y-%m-%d %H:%M:%S", instant, utc);
    const std::string offset_text =
        absl::FormatTime("%Y-%m-%d %H:%M:%S", instant, absl::FixedTimeZone(3600));
    const bool utc_ok = utc_loaded && utc_text == "2023-11-14 22:13:20";
    const bool offset_ok = offset_text == "2023-11-14 23:13:20";
    printk("ABSL_TIME_TEST utc=%d offset=%d unsupported_zone=%d\n", utc_ok, offset_ok,
           new_york_rejected);
    return utc_ok && offset_ok && new_york_rejected;
}
}  // namespace

static int run_test() {
    printk("absl: test driver started\n");
    const bool allocator_ok = test_allocator_arenas();
    printk("absl: allocator result %d\n", allocator_ok);
    const bool synchronization_ok = test_mutex_and_condition_variable();
    printk("ABSL_PORT_TEST allocator=%d sync=%d\n", allocator_ok, synchronization_ok);
    const bool time_ok = test_time_formatting();
    return allocator_ok && synchronization_ok && time_ok ? 0 : 1;
}

int main() {
    printk("absl: starting driver\n");
    int result = 1;
    std::thread driver([&] { result = run_test(); });
    driver.join();
    return result;
}
