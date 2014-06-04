from threading import Condition, RLock


class Monitor:
    '''
    Provide an interface for an externally scheduling monitor.

    Use @mutex to declare that a method requires mutual exclusion.
    
    Use accept(method1, method2, ...) to provide synchornization. Calling
    accept will put the current thread to sleep and only allow calls to
    method1, method2, ... into the monitor. After method1 or method2 or ...
    have finished running the thread that was waiting will be notified.
    '''
    def __init__(self):
        self._active = False
        self._lock = RLock()
        self._entry_queue = []
        self._mutex_queue = {}
        self._mutex_queue_count = {}
        self._accept_stack = []
        self._acceptor_stack = []

    @staticmethod
    def mutex(func):
        '''
        A decorator that wraps a method in an entry/exit protocol in order to
        provide mutual exclusion to that method.

        The entry protocol checks if the monitor is inactive or if the monitor
        is accepting calls to a particular calling method. If so the monitor is
        marked as active and the method can begin execution. If not, the method
        is placed on a queue and the thread is put on a condition.

        The original method is called after the entry protocol is completed.

        The exit protocol is concerned with selecting and notifying the next
        appropriate condition. Priority is given first to any threads who have
        called the accept method, then to any methods waiting that have also
        been flagged by an accept call and then finally to any methods waiting
        in the entry queue. If there are no waiting threads the monitor is
        simply marked as inactive.

        The result of the original method call is returned after the exit
        protocol has completed.
        '''
        def wrap(self, *args, **kwargs):
            if func.__name__ not in self._mutex_queue:
                self._mutex_queue[func.__name__] = Condition(self._lock)
                self._mutex_queue_count[func.__name__] = 0

            result = None
            with self._lock:
                # Entry protocol
                if self._active or self._accept_stack and not func.__name__ in self._accept_stack[-1]:
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
                    self._acceptor_stack.pop().notify()
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
        return wrap

    def accept(self, *args):
        '''
        Provide synchornization through external scheduling. The current thread
        will be put to sleep and the monitor will only allow calls into the
        methods listed in args. Once a call to any of the methods in args has
        been completed the waiting thread will be notified.
        '''
        self._accept_stack.append([func.__name__ for func in args])

        # Use a new condition each time to construct a stack, as opposed to a queue
        cond = Condition(self._lock)
        self._acceptor_stack.append(cond) 

        notified = False
        for func in args:
            if self._mutex_queue_count.get(func.__name__, 0):
                self._mutex_queue[func.__name__].notify()
                notified = True
                break

        self._active = notified
        cond.wait()
