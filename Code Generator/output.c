#include <stdio.h>
#include <stdbool.h>

typedef struct {
    i32 f0;
    bool f1;
} tuple_i32_bool;

void no_return(int x);
tuple_i32_bool combine(int a, int b);
int nested(int x, int y);
void main();

void no_return(int x) {
    printf(""No return, x = {x}"
", );
}

tuple_i32_bool combine(int a, int b) {
    int sum = (a + b);
    bool flag = (sum != 0);
    return (tuple){.f0 = sum, .f1 = flag};
}

int nested(int x, int y) {
    if (((x < y) && ((y > x) || ))) {
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
        }
        count = (count + 1);
    }
    int idx = 0;
    while (1) {
        if ((idx == mixed[1])) {
        }
        printf(""idx: {0}, beta: {1}"
", , );
        idx = (idx + 1);
    }
    int data = combine();
    printf(""combine: {0}, {1}"
", , );
    int f = nested();
    printf(""nested result %d"
", );
}
