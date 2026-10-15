#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>

static void *return_immediately(void *unused) {
    (void) unused;
    return NULL;
}

int main(void) {
    enum { births = 200, concurrent = 8 };
    pthread_t threads[concurrent];
    for (int created = 0; created < births;) {
        int batch = births - created < concurrent ? births - created : concurrent;
        for (int index = 0; index < batch; ++index) {
            if (pthread_create(&threads[index], NULL, return_immediately, NULL) != 0) {
                perror("pthread_create");
                return 2;
            }
        }
        for (int index = 0; index < batch; ++index) {
            if (pthread_join(threads[index], NULL) != 0) {
                perror("pthread_join");
                return 3;
            }
        }
        created += batch;
    }
    puts("THREAD_BIRTH_FIXTURE_OK 200");
    return 0;
}
