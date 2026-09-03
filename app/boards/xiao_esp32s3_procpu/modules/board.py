from machine import unique_id
from zephyr import shell_exec

DEVICE_ID = 0
ID_LEN = 2
uid = unique_id()

for i in range(len(uid)):
    DEVICE_ID ^= (uid[i] << (8*(i%ID_LEN)))

def reboot():
    shell_exec("kernel reboot")
