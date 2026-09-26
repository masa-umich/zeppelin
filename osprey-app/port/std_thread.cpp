/* Thread and synchronization ABI for Zephyr's single-thread libstdc++ build. */
#define _GLIBCXX_THREAD_IMPL
#ifndef _GLIBCXX_HAVE_TLS
#define _GLIBCXX_HAVE_TLS 1
#endif
#include <cxxabi.h>
#include <errno.h>
#include <pthread.h>

#include <condition_variable>
#include <cstdlib>
#include <exception>
#include <functional>
#include <mutex>
#include <thread>

extern "C" struct k_thread z_main_thread;

namespace {
pthread_mutex_t once_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t once_condition = PTHREAD_COND_INITIALIZER;
}  // namespace

int __gthread_once(__gthread_once_t* once, void (*func)(void)) {
    int error = pthread_mutex_lock(&once_mutex);
    if (error != 0) return error;

    while (once->state == 1) {
        error = pthread_cond_wait(&once_condition, &once_mutex);
        if (error != 0) {
            (void)pthread_mutex_unlock(&once_mutex);
            return error;
        }
    }
    if (once->state == 2) {
        (void)pthread_mutex_unlock(&once_mutex);
        return 0;
    }

    once->state = 1;
    (void)pthread_mutex_unlock(&once_mutex);

#if __cpp_exceptions
    try {
        func();
    } catch (...) {
        (void)pthread_mutex_lock(&once_mutex);
        once->state = 0;
        (void)pthread_cond_broadcast(&once_condition);
        (void)pthread_mutex_unlock(&once_mutex);
        throw;
    }
#else
    func();
#endif

    (void)pthread_mutex_lock(&once_mutex);
    once->state = 2;
    (void)pthread_cond_broadcast(&once_condition);
    (void)pthread_mutex_unlock(&once_mutex);
    return 0;
}

namespace std {
_GLIBCXX_BEGIN_NAMESPACE_VERSION

__thread void* __once_callable;
__thread void (*__once_call)();

extern "C" void __once_proxy() { __once_call(); }

namespace {

void* execute_native_thread_routine(void* argument) {
    auto* state = static_cast<thread::_State*>(argument);
#if __cpp_exceptions
    try {
        state->_M_run();
    } catch (...) {
        std::terminate();
    }
#else
    state->_M_run();
#endif
    delete state;
    return nullptr;
}

__gthread_key_t at_thread_exit_key;
__gthread_once_t at_thread_exit_once = __GTHREAD_ONCE_INIT;
int at_thread_exit_key_error;
int at_thread_exit_atexit_error;

struct cxa_thread_exit_elt {
    cxa_thread_exit_elt* next;
    void (*destructor)(void*);
    void* object;
};

struct thread_exit_context {
    cxa_thread_exit_elt* cxa_head;
    __at_thread_exit_elt* callback_head;
};

__thread thread_exit_context current_thread_exit_context;

void run_at_thread_exit(void* value) {
    auto* context = static_cast<thread_exit_context*>(value);
    if (context == nullptr) return;

    // Pop one callback at a time so callbacks registered by a destructor are
    // placed at the head and run before older pending callbacks, as required
    // for LIFO C++ thread-local destruction.
    while (context->cxa_head != nullptr || context->callback_head != nullptr) {
        if (context->cxa_head != nullptr) {
            auto* element = context->cxa_head;
            context->cxa_head = element->next;
            auto destructor = element->destructor;
            void* object = element->object;
            std::free(element);
#if __cpp_exceptions
            try {
                destructor(object);
            } catch (...) {
                std::terminate();
            }
#else
            destructor(object);
#endif
        } else {
            auto* element = context->callback_head;
            context->callback_head = element->_M_next;
            element->_M_cb(element);
        }
    }
}

void run_main_thread_at_exit() { run_at_thread_exit(&current_thread_exit_context); }

void initialize_at_thread_exit_key() {
    at_thread_exit_key_error =
        __gthread_key_create(&at_thread_exit_key, run_at_thread_exit);
    if (at_thread_exit_key_error == 0) {
        at_thread_exit_atexit_error = std::atexit(run_main_thread_at_exit);
    }
}

int ensure_at_thread_exit_key() {
    int error = __gthread_once(&at_thread_exit_once, initialize_at_thread_exit_key);
    if (error != 0) return error;
    if (at_thread_exit_key_error != 0) return at_thread_exit_key_error;
    return at_thread_exit_atexit_error == 0 ? 0 : ENOMEM;
}

int attach_current_thread_exit_context() {
    if (__gthread_getspecific(at_thread_exit_key) != nullptr) return 0;

    const int error =
        __gthread_setspecific(at_thread_exit_key, &current_thread_exit_context);
    // Zephyr's native main thread is not in its POSIX thread pool, so pthread
    // keys reject it. Its registered atexit handler drains the same TLS list.
    return error == EINVAL && k_current_get() == &z_main_thread ? 0 : error;
}

void register_at_thread_exit(__at_thread_exit_elt* element) {
    int error = ensure_at_thread_exit_key();
    if (error != 0) __throw_system_error(error);
    error = attach_current_thread_exit_context();
    if (error != 0) __throw_system_error(error);

    element->_M_next = current_thread_exit_context.callback_head;
    current_thread_exit_context.callback_head = element;
}

int register_cxa_thread_exit(void (*destructor)(void*), void* object) noexcept {
    if (destructor == nullptr) return -1;

    const int error = ensure_at_thread_exit_key();
    if (error != 0) return -1;
    if (attach_current_thread_exit_context() != 0) return -1;

    auto* element =
        static_cast<cxa_thread_exit_elt*>(std::malloc(sizeof(cxa_thread_exit_elt)));
    if (element == nullptr) return -1;

    element->destructor = destructor;
    element->object = object;
    element->next = current_thread_exit_context.cxa_head;
    current_thread_exit_context.cxa_head = element;
    return 0;
}

struct at_thread_exit_notifier final : __at_thread_exit_elt {
    at_thread_exit_notifier(condition_variable& condition, unique_lock<mutex>& lock)
        : condition(&condition), mutex_ptr(lock.mutex()) {
        _M_cb = &at_thread_exit_notifier::run;
        register_at_thread_exit(this);
        (void)lock.release();
    }

    ~at_thread_exit_notifier() {
        mutex_ptr->unlock();
        condition->notify_all();
    }

    static void run(void* element) {
        delete static_cast<at_thread_exit_notifier*>(element);
    }

    condition_variable* condition;
    mutex* mutex_ptr;
};

}  // namespace

int cxa_thread_atexit_impl(void (*destructor)(void*), void* object) noexcept {
    return register_cxa_thread_exit(destructor, object);
}

thread::_State::~_State() = default;

void thread::_M_start_thread(_State_ptr state, void (*dependency)()) {
    // Preserve libstdc++'s link dependency hook even though the Zephyr gthread
    // backend uses strong pthread references instead of weak aliases.
    asm volatile("" : : "rm"(dependency));

    const int error =
        __gthread_create(&_M_id._M_thread, &execute_native_thread_routine, state.get());
    if (error != 0) __throw_system_error(error);
    state.release();
}

void thread::join() {
    if (!joinable()) __throw_system_error(EINVAL);
    const int error = __gthread_join(_M_id._M_thread, nullptr);
    if (error != 0) __throw_system_error(error);
    _M_id = id();
}

void thread::detach() {
    if (!joinable()) __throw_system_error(EINVAL);
    const int error = __gthread_detach(_M_id._M_thread);
    if (error != 0) __throw_system_error(error);
    _M_id = id();
}

unsigned int thread::hardware_concurrency() noexcept {
    // The supported Osprey STM32H723ZG is a single-core microcontroller.
    return 1;
}

condition_variable::condition_variable() noexcept : _M_cond() {}

condition_variable::~condition_variable() noexcept = default;

void condition_variable::notify_one() noexcept { _M_cond.notify_one(); }

void condition_variable::notify_all() noexcept { _M_cond.notify_all(); }

void condition_variable::wait(unique_lock<mutex>& lock) {
    if (!lock.owns_lock()) __throw_system_error(EINVAL);
    _M_cond.wait(*lock.mutex());
}

void notify_all_at_thread_exit(condition_variable& condition, unique_lock<mutex> lock) {
    (void)new at_thread_exit_notifier(condition, lock);
}

_GLIBCXX_END_NAMESPACE_VERSION
}  // namespace std

/*
 * The SDK's libsupc++ was built for a single thread, so its guard routines do
 * not serialize concurrent initialization of function-local statics. Use the
 * ARM EABI guard bits and Zephyr pthread synchronization instead. The pending
 * state is set only while holding this lock; constructors run without it.
 */
namespace {
pthread_mutex_t static_guard_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_cond_t static_guard_condition = PTHREAD_COND_INITIALIZER;
}  // namespace

extern "C" int __cxa_guard_acquire(__cxxabiv1::__guard* guard) {
    if (__atomic_load_n(guard, __ATOMIC_ACQUIRE) & 1) return 0;

    (void)pthread_mutex_lock(&static_guard_mutex);
    if (__atomic_load_n(guard, __ATOMIC_ACQUIRE) & 1) {
        (void)pthread_mutex_unlock(&static_guard_mutex);
        return 0;
    }
    while (__atomic_load_n(guard, __ATOMIC_RELAXED) & 2) {
        __atomic_fetch_or(guard, 4, __ATOMIC_RELAXED);
        (void)pthread_cond_wait(&static_guard_condition, &static_guard_mutex);
        if (__atomic_load_n(guard, __ATOMIC_ACQUIRE) & 1) {
            (void)pthread_mutex_unlock(&static_guard_mutex);
            return 0;
        }
    }
    __atomic_fetch_or(guard, 2, __ATOMIC_RELAXED);
    (void)pthread_mutex_unlock(&static_guard_mutex);
    return 1;
}

extern "C" void __cxa_guard_release(__cxxabiv1::__guard* guard) {
    (void)pthread_mutex_lock(&static_guard_mutex);
    __atomic_store_n(guard, 1, __ATOMIC_RELEASE);
    (void)pthread_cond_broadcast(&static_guard_condition);
    (void)pthread_mutex_unlock(&static_guard_mutex);
}

extern "C" void __cxa_guard_abort(__cxxabiv1::__guard* guard) {
    (void)pthread_mutex_lock(&static_guard_mutex);
    __atomic_store_n(guard, 0, __ATOMIC_RELEASE);
    (void)pthread_cond_broadcast(&static_guard_condition);
    (void)pthread_mutex_unlock(&static_guard_mutex);
}

/*
 * The Zephyr SDK's space-optimized libsupc++ was built with its single-thread
 * configuration. Its eh_globals.o therefore returns one process-wide
 * __cxa_eh_globals object. Exception bookkeeping must be per thread once the
 * gthread backend above enables real pthreads. Match GCC's ARM EH ABI layout:
 * caught exception, uncaught count, and the ARM-EABI propagating exception.
 */
namespace __cxxabiv1 {
struct __cxa_eh_globals {
    __cxa_exception* caughtExceptions;
    unsigned int uncaughtExceptions;
    __cxa_exception* propagatingExceptions;
};
}  // namespace __cxxabiv1

static_assert(sizeof(__cxxabiv1::__cxa_eh_globals) == 3 * sizeof(void*),
              "unexpected ARM EABI exception globals layout");

namespace {
__thread __cxxabiv1::__cxa_eh_globals thread_exception_globals;
}

extern "C" __cxxabiv1::__cxa_eh_globals* __cxa_get_globals() noexcept {
    return &thread_exception_globals;
}

extern "C" __cxxabiv1::__cxa_eh_globals* __cxa_get_globals_fast() noexcept {
    return &thread_exception_globals;
}

extern "C" int __cxa_thread_atexit(void (*destructor)(void*), void* object,
                                   void* dso_handle) noexcept {
    (void)dso_handle;
    return std::cxa_thread_atexit_impl(destructor, object);
}
