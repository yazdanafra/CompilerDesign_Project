#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

typedef struct {
    int f0;
    int f1;
} tuple_i32_i32;



int factorial(int n);
tuple_i32_i32 swap(int a, int b);
void print_message();
int sum_array(int* arr);
void main();

int factorial(int n) {
    if ((n <= 1)) {
        return 1;
    }
    else {
        return (n * factorial((n - 1)));
    }
}

tuple_i32_i32 swap(int a, int b) {
    tuple_i32_i32 tmp = {b, a};
    return tmp;
}

void print_message() {
    printf("Hello from Trust!\n");
}

int sum_array(int* arr) {
    return ((((arr[1 - 1] + arr[2 - 1]) + arr[3 - 1]) + arr[4 - 1]) + arr[5 - 1]);
}

void main() {
    int x = 5;
    int f = factorial(x);
    printf("factorial %d = %d\n", x, f);
    int a = swap(3, 4).f0;
    int b = swap(3, 4).f1;
    printf("swap(3,4) = (%d, %d)\n", a, b);
    int arr[5] = {10, 20, 30, 40, 50};
    int total = sum_array(arr);
    printf("sum of array = %d\n", total);
    if ((total > 100)) {
        printf("Total is large: %d\n", total);
    }
    else {
        printf("Total is modest: %d\n", total);
    }
    int idx = 1;
    while (1) {
        if ((idx > 3)) {
            break;
        }
        if ((idx == 2)) {
            idx = (idx + 1);
        }
        printf("idx = %d\n", idx);
        idx = (idx + 1);
    }
}
