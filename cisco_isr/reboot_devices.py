from nornir import InitNornir
from nornir.plugins.tasks import networking
from nornsible import InitNornsible, nornsible_task
from nornir.core.task import Result
import subprocess
from time import sleep  
from termcolor import colored
import os

NORNIR_CONFIG_FILE = os.environ['NORNIR_CONFIG_FILE']

@nornsible_task
def commit_config(task):
    """
    Write Config Prior to Reboot
    """
    print(colored(f'Writing config on {task.host.name}', 'yellow'))
    task.run(task=networking.netmiko_save_config)

@nornsible_task
def reboot_device(task):
    """
    Reboots the device
    """
    print(colored(f'Rebooting {task.host.name}', 'yellow'))
    task.run(
        task=networking.netmiko_send_command, 
        command_string='reload', 
        **{'expect_string': '[confirm]'}
        )
    task.run(task=networking.netmiko_send_command, use_timing=True, command_string= '\n')
    task.host.close_connections()

@nornsible_task
def ping_until_up(task): 
    """
    Ping the device every 5 seconds until back up. If pings
    stop responding after 20 minutes, log error message to terminal
    """
    print(colored(f'Waiting for {task.host.name} to reboot', 'yellow'))
    seconds = 1200
    while True:
        response = subprocess.call(['ping', '-c', '1', task.host.name], stdout=subprocess.PIPE)
        if response != 0:
            sleep(5)
            seconds = seconds - 5
            if seconds <= 0:
                result = f"***** WARNING ***** {task.host} didn't respond to a ping within 20 minutes"
                print(colored(result, 'red'))
                result = Result(host=task.host, changed=True, Failed=True, result=result)
                break
            else:
                continue
        elif response == 0:
            result = f'{task.host.name} is now responding to ping. The device was down for about {1200 - seconds} seconds.'
            print(colored(result, 'green'))
            result = Result(host=task.host, changed=False, Failed=False, result=result)
            break
    return result

def main():
    nr = InitNornir(config_file=NORNIR_CONFIG_FILE)
    nr = InitNornsible(nr)
    nr.run(task=commit_config)
    nr.run(task=reboot_device)
    nr.run(task=ping_until_up)
    

if __name__ == "__main__":
    main()
