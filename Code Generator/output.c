#include <stdio.h>
#include <stdbool.h>

int* make_seq();
void main();

int* make_seq() {
    int arr[4] = {1, 2, 3, 4};
    return arr;
}

void main() {
    int* seq = make_seq();
    int a = seq[0];
    int b = seq[2];
    int c = seq[3];
    printf("seq = %d, %d, %d\n", a, b, c);
}
