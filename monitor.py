from inspect import getmembers
from threading import Condition, Lock, RLock


class ConditionStack:
    '''
    A LIFO Condition.

    The interface is a partial copy of threading.Condition.
    However, the Condition must be acquired using the with statement.
    '''
    def __init__(self, lock=None):
        if lock is None:
            lock = RLock()
        self._lock = lock
        self._waiters = []

    def __enter__(self):
        self._lock.__enter__()

    def __exit__(self, *args):
        self._lock.__exit__(*args)

    def wait(self):
        if not self._lock._is_owned():
            raise RuntimeError("cannot wait on un-acquired lock")
        waiter = Lock()
        waiter.acquire()
        self._waiters.append(waiter)
        self._lock.release()
        try:
            waiter.acquire()
            return True
        finally:
            self._lock.acquire()

    def notify(self):
        if not self._lock._is_owned():
            raise RuntimeError("cannot notify on un-acquired lock")
        if self._waiters:
            waiter = self._waiters.pop()
            waiter.release()


class Monitor:
    '''
    Provide high-level mutual exclusion and synchornization.

    Use @Monitor.mutex to designate a method requiring mutual exclusion
    and use accept() to force synchornization.

    Only one thread of execution may be inside any of the mutex methods
    at any given time. Additional calls to any mutex methods will queue
    up outside those methods and execute in FIFO order as threads exit
    the mutex methods.

    The accept() method can be used to choose what methods the monitor
    will allow to execute. That is, accept(foo, bar) will put the
    monitor in a state where only calls to foo() and bar() will be
    allowed to execute, all other calls will queue up outside the
    methods until a call to foo or bar has been completed. The
    thread that calls accept() will be put to sleep until one of the
    acceptable methods has returned. It is worth noting that any
    methods passed to accept() must be mutex methods.
    '''
    def __init__(self):
        self._active = False
        self._lock = RLock()
        self._entry_queue = []
        self._mutex_queue = {}
        self._mutex_queue_count = {}
        self._accept_stack = []
        self._acceptor_stack = ConditionStack(self._lock)

        for name, member in getmembers(self, lambda m: getattr(m, '_mutex', 0)):
            self._mutex_queue[name] = Condition(self._lock)
            self._mutex_queue_count[name] = 0

    @staticmethod
    def mutex(func):
        '''
        A decorator that wraps a method in an entry/exit protocol in
        order to provide mutual exclusion to that method.

        The entry protocol checks if the monitor is inactive or if the
        monitor is accepting calls to a particular calling method. If
        so the monitor is marked as active and the method can begin
        execution. If not, the method is placed on a queue and the
        thread is put on a condition.

        The original method is called after the entry protocol is
        completed.

        The exit protocol is concerned with selecting and notifying the
        next appropriate condition. Priority is given first to any
        threads who have called the accept method, then to any methods
        waiting that have also been flagged by an accept call and then
        finally to any methods waiting in the entry queue. If there are
        no waiting threads the monitor is simply marked as inactive.

        The result of the original method call is returned after the
        exit protocol has completed.
        '''
        def wrap(self, *args, **kwargs):
            result = None
            with self._lock:
                # Entry protocol
                if (self._active or self._accept_stack and
                        func.__name__ not in self._accept_stack[-1]):
                    # The monitor is active or not currently accepting calls to this method
                    self._entry_queue.append(func.__name__)
                    self._mutex_queue_count[func.__name__] += 1
                    self._mutex_queue[func.__name__].wait()
                    self._mutex_queue_count[func.__name__] -= 1
                    self._entry_queue.remove(func.__name__)
                self._active = True

                # Run the actual method, store the result
                result = func(self, *args, **kwargs)

                # Exit protocol
                if self._accept_stack and func.__name__ in self._accept_stack[-1]:
                    # Signal thread in acceptor stack
                    self._accept_stack.pop()
                    self._acceptor_stack.notify()
                elif self._accept_stack:
                    for f in self._accept_stack[-1]:
                        # Signal mutex queue
                        if self._mutex_queue_count.get(f, 0):
                            self._mutex_queue[f].notify()
                            break
                elif self._entry_queue:
                    # signal entry queue
                    self._mutex_queue[self._entry_queue[0]].notify()
                else:
                    self._active = False

            return result

        wrap.__name__ = func.__name__
        wrap._mutex = True
        return wrap

    def accept(self, *funcs):
        '''
        Puts the calling thread to sleep and puts the monitor in a
        state such that the monitor will only allow calls to methods
        that are in *funcs to execute.

        Once a call to one of the methods in *funcs has returned, the
        monitor will revert to it's previous state (accepting all
        methods or a previous accept state) and the thread that was
        put to sleep will be notified.

        Must be called from inside a mutex method.

        *funcs must only contain mutex methods.
        '''
        self._accept_stack.append([func.__name__ for func in funcs])

        notified = False
        for func in funcs:
            if self._mutex_queue_count.get(func.__name__, 0):
                self._mutex_queue[func.__name__].notify()
                notified = True
                break

        self._active = notified
        self._acceptor_stack.wait()
