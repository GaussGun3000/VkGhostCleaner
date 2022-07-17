from datetime import datetime


class Logger:
    def __init__(self):
        self.file = open(file='log.txt', mode='w+')

    def log(self, message: str):
        time = datetime.now()
        logstr = f'[{time.strftime("%H:%M:%S")}]: {message}\n'
        self.file.write(logstr)

    def close(self):
        self.file.close()
