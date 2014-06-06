'''
A dining philosophers solution using a monitor.
http://en.wikipedia.org/wiki/Dining_philosophers
'''

from random import randint, seed
from threading import Thread, active_count
from time import sleep, time
import sys
sys.path.append("..")  # So that monitor can be imported

from monitor import Monitor


class Table(Monitor):
    def __init__(self, philosophers):
        super().__init__()
        self.philosophers = philosophers
        self.forks = [False] * philosophers

    @Monitor.mutex
    def pick_up_forks(self, philosopher):
        right = philosopher
        left = (philosopher + 1) % self.philosophers
        while self.forks[right] or self.forks[left]:
            self.accept(self.pick_up_forks, self.put_down_forks)
        self.forks[right] = True
        self.forks[left] = True
        print('{} pick up {}, {}'.format(philosopher, right, left))

    @Monitor.mutex
    def put_down_forks(self, philosopher):
        right = philosopher
        left = (philosopher + 1) % self.philosophers
        self.forks[left] = False
        self.forks[right] = False
        print('{} put down {}, {}'.format(philosopher, right, left))


class Philosopher(Thread):
    def __init__(self, id_, table):
        super().__init__()
        self.id = id_
        self.table = table
        self.spaghetti = 100

    def run(self):
        while self.spaghetti > 0:
            for n in range(randint(5, 10)):
                sleep(0)
            self.table.pick_up_forks(self.id)
            self.spaghetti -= min(self.spaghetti, randint(1, 10))
            self.table.put_down_forks(self.id)


if __name__ == "__main__":
    seed(time())
    table = Table(5)
    for n in range(5):
        p = Philosopher(n, table)
        p.start()

    while active_count() > 1:
        sleep(0)
