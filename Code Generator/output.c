#include <stdio.h>
#include <stdbool.h>

int add(int x, int y);
void main();

int add(int x, int y) {
    return (x + y);
}

void main() {
    int z = add(2, 3);
    printf("z = %d\n", z);
}
