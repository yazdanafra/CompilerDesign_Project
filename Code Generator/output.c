#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>



bool is_even(int x);
int sum_array(int* a);
int find_first_even(int* a);
int count_pairs(int n, int target);
void main();

bool is_even(int x) {
    return ((x % 2) == 0);
}

int sum_array(int* a) {
    int total = 0;
    int i = 0;
    while (1) {
        if ((i == 5)) {
            break;
        }
        total = (total + a[i]);
        i = (i + 1);
    }
    return total;
}

int find_first_even(int* a) {
    int i = 0;
    while (1) {
        if ((i == 5)) {
            break;
        }
        if (is_even(a[i])) {
            return i;
        }
        i = (i + 1);
    }
    return -1;
}

int count_pairs(int n, int target) {
    int count = 0;
    int i = 0;
    while (1) {
        if ((i == n)) {
            break;
        }
        int j = 0;
        while (1) {
            if ((j == n)) {
                break;
            }
            if (((i + j) == target)) {
                count = (count + 1);
            }
            j = (j + 1);
        }
        i = (i + 1);
    }
    return count;
}

void main() {
    int nums[5] = {3, 4, 7, 8, 10};
    printf("Array is_even flags:\n");
    int k = 0;
    while (1) {
        if ((k == 5)) {
            break;
        }
        printf("  %d → %d\n", nums[k], is_even(nums[k]));
        k = (k + 1);
    }
    int total = sum_array(nums);
    printf("Sum of array = %d\n", total);
    int idx = find_first_even(nums);
    if ((idx >= 0)) {
        printf("First even at index %d (value %d)\n", idx, nums[idx]);
    }
    else {
        printf("No even numbers found\n");
    }
    int pairs = count_pairs(5, 7);
    printf("Number of (i,j) in [0..5)² summing to 7 = %d\n", pairs);
}
