import sys
import pathlib
import io

class _writer(io.TextIOBase):
    def __init__(self, *targets):
        super().__init__()
        self.targets = targets

    def write(self, content):
        for target in self.targets:
            target.write(content)
            target.flush()
    
    def flush(self):
        for target in self.targets:
            target.flush()

class LogWriter:

    def __init__(self, file, capture_stdout=True, capture_stderr=True):
        self.logpath = pathlib.Path(file)
        self.capture_stdout = capture_stdout
        self.capture_stderr = capture_stderr

    def __enter__(self):
        if not self.logpath.exists():
            self.logpath.touch()
        self.logobj = open(self.logpath._str, "a")
        if self.capture_stdout:
            self.initial_stdout = sys.stdout
            sys.stdout = _writer(sys.stdout, self.logobj)
        if self.capture_stderr:
            self.initial_stderr = sys.stderr
            sys.stderr = _writer(sys.stderr, self.logobj)

    def __exit__(self, type, value, traceback):
        if self.capture_stdout:
            sys.stdout.flush()
            sys.stdout = self.initial_stdout
        if self.capture_stderr:
            sys.stderr.flush()
            sys.stderr = self.initial_stderr
        self.logobj.close()
