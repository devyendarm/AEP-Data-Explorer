from PySide6.QtCore import QObject, Signal, QThread
from auth import AEPAuthHandler
from logger import logger

class ApiWorker(QThread):
    """
    Generic worker thread for running API calls in the background.
    """
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            # Pass progress callback if the function accepts it
            import inspect
            sig = inspect.signature(self.func)
            if 'progress_callback' in sig.parameters:
                self.kwargs['progress_callback'] = self.progress.emit
            
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Worker thread error: {e}", exc_info=True)
            self.error.emit(str(e))

class ApiService(QObject):
    """
    Base service for managing API interactions.
    """
    def __init__(self):
        super().__init__()
        self.auth = AEPAuthHandler()

    def run_async(self, func, on_success=None, on_error=None, *args, **kwargs):
        """
        Helper to run a function in a background thread.
        """
        worker = ApiWorker(func, *args, **kwargs)
        if on_success:
            worker.finished.connect(on_success)
        if on_error:
            worker.error.connect(on_error)
        
        # Keep a reference to avoid garbage collection
        # In a real app, you might want a thread pool or manager
        self._worker = worker 
        worker.start()
        return worker
