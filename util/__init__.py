import os

# Exception safe
def exists(path) -> bool:
    return os.access(path, os.F_OK)

# Exception safe
def accessible(path) -> bool:
    return os.access(path, os.R_OK | os.W_OK | os.X_OK)

# Throws FileNotFoundError if path does not exist
# Throws PermissionError if the user lacks
#   required permissions to list the directory
# Throws NotADirectoryError if the path is not a directory
def emptyDir(path) -> bool:
    return not os.listdir(path)
