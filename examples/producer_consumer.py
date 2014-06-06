from threading import Thread
import sys
sys.path.append("..")

from monitor import Monitor


class BoundedBuffer(Monitor):
    def __init__(self, size):
        super().__init__()
        self._buffer = [None] * size
        self._head = 0
        self._tail = 0
        self._count = 0
        self._size = size

    @Monitor.mutex
    def push(self, data):
        if self._count == self._size:
            self.accept(self.pop)

        self._count += 1
        self._buffer[self._head] = data
        self._head = (self._head + 1) % self._size

    @Monitor.mutex
    def pop(self):
        if self._count == 0:
            self.accept(self.push)

        data = self._buffer[self._tail]
        self._tail = (self._tail + 1) % self._size
        self._count -= 1
        return data

    @property
    def count(self):
        return self._count


class Producer(Thread):
    def __init__(self, id_, buffer_):
        super().__init__()
        self.id = id_
        self.buffer = buffer_
        self.start()  # Autostart thread

    def run(self):
        for n in range(10):
            print('{} P {}'.format(self.id, n))
            self.buffer.push(n)


class Consumer(Thread):
    def __init__(self, id_, buffer_):
        super().__init__()
        self.id = id_
        self.buffer = buffer_
        self.start()  # Autostart thread

    def run(self):
        data = self.buffer.pop()
        while data != -1:
            print('{} C {}'.format(self.id, data))
            data = self.buffer.pop()


if __name__ == "__main__":
    buffer_ = BoundedBuffer(10)
    producers = [Producer(n, buffer_) for n in range(5)]
    consumers = [Consumer(n, buffer_) for n in range(5)]

    # Wait for producers to finish
    for producer in producers:
        producer.join()

    # Signal consumers to finish
    for n in range(len(producers)):
        buffer_.push(-1)

    # Wait for consumers to finish
    for consumer in consumers:
        consumer.join()
