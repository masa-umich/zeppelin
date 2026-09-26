#include <zephyr/kernel.h>
#include <zephyr/sys/barrier.h>

#include <cstdint>
#include <type_traits>

namespace {

// Cortex-M7 is a single core and has no naturally atomic 64-bit accesses.
// Masking interrupts through the kernel spinlock serializes thread and ISR
// callers; the barriers make the ABI operations sequentially consistent.
struct k_spinlock atomic64_lock{};

uint64_t load_locked(const volatile void* address) {
    return *static_cast<const volatile uint64_t*>(address);
}

void store_locked(volatile void* address, uint64_t value) {
    *static_cast<volatile uint64_t*>(address) = value;
}

enum class Update {
    add,
    sub,
    bit_and,
    bit_or,
    bit_xor,
    bit_nand,
};

uint64_t update_locked(volatile void* address, uint64_t operand, Update op) {
    const uint64_t old_value = load_locked(address);
    uint64_t new_value;
    switch (op) {
        case Update::add:
            new_value = old_value + operand;
            break;
        case Update::sub:
            new_value = old_value - operand;
            break;
        case Update::bit_and:
            new_value = old_value & operand;
            break;
        case Update::bit_or:
            new_value = old_value | operand;
            break;
        case Update::bit_xor:
            new_value = old_value ^ operand;
            break;
        case Update::bit_nand:
            new_value = ~(old_value & operand);
            break;
    }
    store_locked(address, new_value);
    return old_value;
}

template <typename Operation>
auto sequentially_consistent(Operation operation) -> decltype(operation()) {
    const k_spinlock_key_t key = k_spin_lock(&atomic64_lock);
    barrier_dmem_fence_full();
    if constexpr (std::is_void_v<decltype(operation())>) {
        operation();
        barrier_dmem_fence_full();
        k_spin_unlock(&atomic64_lock, key);
    } else {
        auto result = operation();
        barrier_dmem_fence_full();
        k_spin_unlock(&atomic64_lock, key);
        return result;
    }
}

}  // namespace

// GCC's generic atomic ABI passes memory-order values to these helpers.
// Applying sequential consistency for every order is stronger than required
// and keeps the fallback straightforward on this single-core target.
extern "C" {

uint64_t atomic_load_8_abi(const volatile void* address,
                           int) __asm__("__atomic_load_8");
uint64_t atomic_load_8_abi(const volatile void* address, int) {
    return sequentially_consistent([&] { return load_locked(address); });
}

void atomic_store_8_abi(volatile void* address, uint64_t value,
                        int) __asm__("__atomic_store_8");
void atomic_store_8_abi(volatile void* address, uint64_t value, int) {
    sequentially_consistent([&] { store_locked(address, value); });
}

uint64_t atomic_exchange_8_abi(volatile void* address, uint64_t value,
                               int) __asm__("__atomic_exchange_8");
uint64_t atomic_exchange_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent([&] {
        const uint64_t old_value = load_locked(address);
        store_locked(address, value);
        return old_value;
    });
}

// The GCC frontend builtin takes a weak argument, but its size-specific
// libatomic ABI helper omits it. A private C identifier plus asm label avoids
// colliding with GCC's six-argument builtin declaration.
bool compare_exchange_8_abi(volatile void* address, void* expected, uint64_t desired,
                            int, int) __asm__("__atomic_compare_exchange_8");

bool compare_exchange_8_abi(volatile void* address, void* expected, uint64_t desired,
                            int, int) {
    return sequentially_consistent([&] {
        const uint64_t old_value = load_locked(address);
        auto* expected_value = static_cast<uint64_t*>(expected);
        if (old_value == *expected_value) {
            store_locked(address, desired);
            return true;
        }
        *expected_value = old_value;
        return false;
    });
}

uint64_t atomic_fetch_add_8_abi(volatile void* address, uint64_t value,
                                int) __asm__("__atomic_fetch_add_8");
uint64_t atomic_fetch_add_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::add); });
}

uint64_t atomic_add_fetch_8_abi(volatile void* address, uint64_t value,
                                int) __asm__("__atomic_add_fetch_8");
uint64_t atomic_add_fetch_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::add) + value; });
}

uint64_t atomic_fetch_sub_8_abi(volatile void* address, uint64_t value,
                                int) __asm__("__atomic_fetch_sub_8");
uint64_t atomic_fetch_sub_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::sub); });
}

uint64_t atomic_sub_fetch_8_abi(volatile void* address, uint64_t value,
                                int) __asm__("__atomic_sub_fetch_8");
uint64_t atomic_sub_fetch_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::sub) - value; });
}

uint64_t atomic_fetch_and_8_abi(volatile void* address, uint64_t value,
                                int) __asm__("__atomic_fetch_and_8");
uint64_t atomic_fetch_and_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::bit_and); });
}

uint64_t atomic_and_fetch_8_abi(volatile void* address, uint64_t value,
                                int) __asm__("__atomic_and_fetch_8");
uint64_t atomic_and_fetch_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::bit_and) & value; });
}

uint64_t atomic_fetch_or_8_abi(volatile void* address, uint64_t value,
                               int) __asm__("__atomic_fetch_or_8");
uint64_t atomic_fetch_or_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::bit_or); });
}

uint64_t atomic_or_fetch_8_abi(volatile void* address, uint64_t value,
                               int) __asm__("__atomic_or_fetch_8");
uint64_t atomic_or_fetch_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::bit_or) | value; });
}

uint64_t atomic_fetch_xor_8_abi(volatile void* address, uint64_t value,
                                int) __asm__("__atomic_fetch_xor_8");
uint64_t atomic_fetch_xor_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::bit_xor); });
}

uint64_t atomic_xor_fetch_8_abi(volatile void* address, uint64_t value,
                                int) __asm__("__atomic_xor_fetch_8");
uint64_t atomic_xor_fetch_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::bit_xor) ^ value; });
}

uint64_t atomic_fetch_nand_8_abi(volatile void* address, uint64_t value,
                                 int) __asm__("__atomic_fetch_nand_8");
uint64_t atomic_fetch_nand_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return update_locked(address, value, Update::bit_nand); });
}

uint64_t atomic_nand_fetch_8_abi(volatile void* address, uint64_t value,
                                 int) __asm__("__atomic_nand_fetch_8");
uint64_t atomic_nand_fetch_8_abi(volatile void* address, uint64_t value, int) {
    return sequentially_consistent(
        [&] { return ~(update_locked(address, value, Update::bit_nand) & value); });
}

}  // extern "C"
