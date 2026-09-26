/* Zephyr pthread backend for libstdc++'s GCC thread abstraction. */
#ifndef _GLIBCXX_GCC_GTHR_H
#define _GLIBCXX_GCC_GTHR_H

#include <time.h>
#include <zephyr/posix/pthread.h>
#include <zephyr/posix/sched.h>

// STM32 HAL headers reached through pthread.h leak a macro that collides with
// protobuf::DescriptorPool::ErrorCollector::OUTPUT_TYPE.
#ifdef OUTPUT_TYPE
#undef OUTPUT_TYPE
#endif
#ifdef CRC
#undef CRC
#endif

#define __GTHREADS 1
#define __GTHREADS_CXX0X 1
#define __GTHREAD_HAS_COND 1
#define _GTHREAD_USE_MUTEX_TIMEDLOCK 1
#define _GLIBCXX_GTHREAD_USE_WEAK 0

typedef pthread_t __gthread_t;
typedef pthread_key_t __gthread_key_t;
typedef struct {
    unsigned int state;
} __gthread_once_t;
typedef pthread_mutex_t __gthread_mutex_t;
typedef pthread_mutex_t __gthread_recursive_mutex_t;
typedef pthread_cond_t __gthread_cond_t;
typedef struct timespec __gthread_time_t;

#define __GTHREAD_ONCE_INIT {0}
#define __GTHREAD_MUTEX_INIT PTHREAD_MUTEX_INITIALIZER
#define __GTHREAD_MUTEX_INIT_FUNCTION __gthread_mutex_init_function
#define __GTHREAD_RECURSIVE_MUTEX_INIT_FUNCTION __gthread_recursive_mutex_init_function
#define __GTHREAD_COND_INIT PTHREAD_COND_INITIALIZER
#define __GTHREAD_TIME_INIT {0, 0}

static inline int __gthread_active_p(void) { return 1; }

int __gthread_once(__gthread_once_t* once, void (*func)(void));

static inline int __gthread_key_create(__gthread_key_t* key, void (*dtor)(void*)) {
    return pthread_key_create(key, dtor);
}

static inline int __gthread_key_delete(__gthread_key_t key) {
    return pthread_key_delete(key);
}

static inline void* __gthread_getspecific(__gthread_key_t key) {
    return pthread_getspecific(key);
}

static inline int __gthread_setspecific(__gthread_key_t key, const void* value) {
    return pthread_setspecific(key, value);
}

static inline void __gthread_mutex_init_function(__gthread_mutex_t* mutex) {
    (void)pthread_mutex_init(mutex, NULL);
}

static inline int __gthread_mutex_destroy(__gthread_mutex_t* mutex) {
    return pthread_mutex_destroy(mutex);
}

static inline int __gthread_mutex_lock(__gthread_mutex_t* mutex) {
    return pthread_mutex_lock(mutex);
}

static inline int __gthread_mutex_trylock(__gthread_mutex_t* mutex) {
    return pthread_mutex_trylock(mutex);
}

static inline int __gthread_mutex_timedlock(__gthread_mutex_t* mutex,
                                            const __gthread_time_t* deadline) {
    return pthread_mutex_timedlock(mutex, deadline);
}

static inline int __gthread_mutex_unlock(__gthread_mutex_t* mutex) {
    return pthread_mutex_unlock(mutex);
}

static inline void __gthread_recursive_mutex_init_function(
    __gthread_recursive_mutex_t* mutex) {
    pthread_mutexattr_t attr;
    int error = pthread_mutexattr_init(&attr);
    if (error != 0) return;

    error = pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
    if (error == 0) (void)pthread_mutex_init(mutex, &attr);
    (void)pthread_mutexattr_destroy(&attr);
}

static inline int __gthread_recursive_mutex_destroy(
    __gthread_recursive_mutex_t* mutex) {
    return pthread_mutex_destroy(mutex);
}

static inline int __gthread_recursive_mutex_lock(__gthread_recursive_mutex_t* mutex) {
    return pthread_mutex_lock(mutex);
}

static inline int __gthread_recursive_mutex_trylock(
    __gthread_recursive_mutex_t* mutex) {
    return pthread_mutex_trylock(mutex);
}

static inline int __gthread_recursive_mutex_timedlock(
    __gthread_recursive_mutex_t* mutex, const __gthread_time_t* deadline) {
    return pthread_mutex_timedlock(mutex, deadline);
}

static inline int __gthread_recursive_mutex_unlock(__gthread_recursive_mutex_t* mutex) {
    return pthread_mutex_unlock(mutex);
}

static inline void __gthread_cond_init_function(__gthread_cond_t* cond) {
    (void)pthread_cond_init(cond, NULL);
}

static inline int __gthread_cond_destroy(__gthread_cond_t* cond) {
    return pthread_cond_destroy(cond);
}

static inline int __gthread_cond_broadcast(__gthread_cond_t* cond) {
    return pthread_cond_broadcast(cond);
}

static inline int __gthread_cond_signal(__gthread_cond_t* cond) {
    return pthread_cond_signal(cond);
}

static inline int __gthread_cond_wait(__gthread_cond_t* cond,
                                      __gthread_mutex_t* mutex) {
    return pthread_cond_wait(cond, mutex);
}

static inline int __gthread_cond_timedwait(__gthread_cond_t* cond,
                                           __gthread_mutex_t* mutex,
                                           const __gthread_time_t* deadline) {
    return pthread_cond_timedwait(cond, mutex, deadline);
}

static inline int __gthread_cond_wait_recursive(__gthread_cond_t* cond,
                                                __gthread_recursive_mutex_t* mutex) {
    return pthread_cond_wait(cond, mutex);
}

static inline int __gthread_create(__gthread_t* thread, void* (*func)(void*),
                                   void* args) {
    return pthread_create(thread, NULL, func, args);
}

static inline int __gthread_join(__gthread_t thread, void** result) {
    return pthread_join(thread, result);
}

static inline int __gthread_detach(__gthread_t thread) {
    return pthread_detach(thread);
}

static inline int __gthread_equal(__gthread_t left, __gthread_t right) {
    return pthread_equal(left, right);
}

static inline __gthread_t __gthread_self(void) { return pthread_self(); }

static inline int __gthread_yield(void) { return sched_yield(); }

#endif /* _GLIBCXX_GCC_GTHR_H */
