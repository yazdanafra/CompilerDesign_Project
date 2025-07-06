#include <stdio.h>
#include <stdbool.h>

void main();

void main() {
    int nums[4] = {10, 20, 30, 40};
    int first = nums[1];
    int middle = nums[2];
    int last = nums[3];
    printf("first = %d, middle = %d, last = %d\n", first, middle, last);
}
