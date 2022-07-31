import os


def exists(path) -> bool:
    return os.access(path, os.F_OK)


def accessible(path) -> bool:
    return os.access(path, os.R_OK | os.W_OK | os.X_OK)


def emptyDir(path) -> bool:
    return not os.listdir(path)
