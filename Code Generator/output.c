#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

typedef struct {
    int f0;
    bool f1;
} tuple_i32_bool;

typedef struct {
    int f0;
    int f1;
} tuple_i32_i32;


bool alpha = true;
bool beta = false;
int gamma = 0;
int delta = -15;
int epsilon = +15;
tuple_i32_bool t1 = {1,false};
tuple_i32_i32 t2 = {2,3};
int unused = 0;
int mixed[3] = {5, 10, 15};
bool flags[2] = {true, false};
int nums[3] = {0x1, 0x2, 0x3};

void no_return(int x);
tuple_i32_bool combine(int a, int b);
int nested(int x, int y);
void main();

void no_return(int x) {
    printf("No return, x = %d\n", x);
}

tuple_i32_bool combine(int a, int b) {
    int sum = (a + b);
    bool flag = (sum != 0);
    tuple_i32_bool tmp = {sum, flag};
    return tmp;
}

int nested(int x, int y) {
    if (((x < y) && ((y > x) || false))) {
        int res = ((x * y) % 7);
        if ((res <= 10)) {
            return res;
        }
        else {
            return (res + 1);
        }
    }
    else {
        return (x - y);
    }
}

void main() {
    int count = 0;
    while (1) {
        if ((count >= 3)) {
            break;
        }
        count = (count + 1);
    }
    int idx = 0;
    while (1) {
        if ((idx == mixed[1 - 1])) {
            break;
        }
        printf("idx: %d, beta: %d\n", idx, beta);
        idx = (idx + 1);
    }
    int res = combine(2, 3).f0;
    bool fl = combine(2, 3).f1;
    printf("combine: %d, %d\n", res, fl);
    int f = nested(4, 2);
    printf("nested result %d\n", f);
}
