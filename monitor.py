from threading import Condition, RLock


class Monitor:
    '''
    Provide an interface for an externally scheduling monitor.

    Use @mutex to declare that a method requires mutual exclusion.
    
    Use accept(method1, method2, ...) to provide synchornization. Calling accept will put the current
    thread to sleep and only allow calls to method1, method2, ... into the monitor. After method1 or
    method2 or ... have finished running the thread that was waiting will be notified.
    '''
    def __init__(self):
        self._active = False
        self._lock = RLock()
        self._entry_queue = []
        self._mutex_queue = {}
        self._mutex_queue_count = {}
        self._condition_queue = {}
        self._acceptor_stack = []
        self._accept_stack = []

    @staticmethod
    def mutex(func):
        ''' A decorator to provide mutual exclusion to methods. '''
        def wrap(self, *args, **kwargs):
            if func not in self._mutex_queue:
                self._mutex_queue[func] = Condition(self._lock)
                self._mutex_queue_count[func] = 0

            with self._lock:
                # Entry protocol
                if self._active or self._accept_stack and not func in self._accept_stack[-1]:
                    self._entry_queue.append(func)
                    self._mutex_queue_count[func] += 1
                    self._mutex_queue[func].wait()
                    self._mutex_queue_count -= 1
                    self._entry_queue.remove(func)
                self.active = True

                result = func(self, *args, **kwargs)
                
                # Exit protocol
                if self._accept_stack and func in self._accept_stack[-1]:
                    # Signal thread in acceptor stack
                    self._accept_stack.pop()
                    self._acceptor_stack.pop().notify()

                elif self._accept_stack:
                    # 
                    for f in self._accept_stack[-1]:
                        # signal mutex queue
                        if self._mutex_queue_count[f]:
                            self._mutex_queue[f].notify()
                            break
                elif self._entry_queue:
                    # signal entry queue
                    self._mutex_queue[self._entry_queue[0]].notify()
                else:
                    self.active = False

            return result
        return wrap

    def accept(self, *args):
        '''
        Provide synchornization through external scheduling. The current thread
        will be put to sleep and the monitor will only allow calls into the methods
        listed in args. Once a call to any of the methods in args has been completed
        the waiting thread will be notified.
        '''
        self._accept_stack.append(args)
        cond = Condition(self._lock)
        self._acceptor_stack.append(cond)
        notified = False
        for func in args:
            if self._mutex_queue_count[func]:
                self._mutex_queue[func].notify()
                notified = True
                break

        active = notified
        cond.wait()
