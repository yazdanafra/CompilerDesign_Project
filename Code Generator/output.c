#include <stdio.h>
#include <stdbool.h>

typedef struct {
    int f0;
    int f1;
} tuple_i32_i32;

typedef struct {
    int f0;
    bool f1;
    int f2;
} tuple_i32_bool_i32;


int counter = 0;
int limit = 5;
bool flags[3] = {true, false, true};
int message[4] = {10, 20, 30, 40};

int factorial(int n);
int sum_and_diff(int a, int b);
tuple_i32_i32 swap(int x, int y);
void main();

int factorial(int n) {
    if ((n <= 1)) {
        return 1;
    }
    else {
        return (n * factorial((n - 1)));
    }
}

int sum_and_diff(int a, int b) {
    int sum = (a + b);
    int diff;
    if ((a >= b)) {
        diff = (a - b);
    }
    else {
        diff = (b - a);
    }
    return (sum + diff);
}

tuple_i32_i32 swap(int x, int y) {
    tuple_i32_i32 tmp = {y, x};
    return tmp;
}

void main() {
    printf("Initial counter = %d\n", counter);
    printf("limit = %d\n", limit);
    printf("flags = %d, %d, %d\n", flags[1], flags[1], flags[2]);
    printf("message = %d, %d, %d, %d\n", message[1], message[1], message[2], message[3]);
    while (1) {
        if ((counter >= limit)) {
            break;
        }
        counter = (counter + 1);
        printf("Counter now = %d\n", counter);
    }
    int fact5 = factorial(5);
    printf("5! = %d\n", fact5);
    int s = sum_and_diff(7, 3);
    printf("sum+diff of (7,3) = %d\n", s);
    int new_a = swap(8, 42).f0;
    int new_b = swap(8, 42).f1;
    printf("after swap: a = %d, b = %d\n", new_a, new_b);
    tuple_i32_i32 pair = {100,200};
    int p = pair.f0;
    int q = pair.f1;
    printf("pair p = %d, q = %d\n", p, q);
    tuple_i32_bool_i32 triple = {5,false,6};
    int t1 = triple.f0;
    bool t_flag = triple.f1;
    int t2 = triple.f2;
    printf("triple: t1 = %d, flag = %d, t2 = %d\n", t1, t_flag, t2);
    printf("All tests passed.\n");
}
