from nornir import InitNornir
from nornir.plugins.tasks import networking
from nornsible import InitNornsible, nornsible_task
from termcolor import colored
import os

NORNIR_CONFIG_FILE = os.environ['NORNIR_CONFIG_FILE']

@nornsible_task
def get_images_in_flash(task):
    """
    Gets the list of images currently in flash by searching for
    Images that have an extension of .bin and assigns to
    nornir device attribute 'images_in_flash' for later use
    """
    result = task.run(
        task=networking.netmiko_send_command, 
        command_string='dir', 
        **{'use_textfsm': True}
    )
    files_list = result[0].result
    images_list = []
    for file in files_list:
        if '.bin' in file['name']:
            images_list.append(file['name'])
    task.host['images_in_flash'] = images_list

@nornsible_task
def get_running_image(task):
    """
    Gets the the current running image and assigns it to nornir
    device attribute for later use
    """
    result = task.run(
        task=networking.netmiko_send_command, 
        command_string='show version', 
        use_textfsm=True
    )
    running_image = result[0].result[0]['running_image']
    running_image = running_image.replace('/', '')
    task.host['running_image'] = running_image

@nornsible_task
def get_images_to_remove(task):
    """
    procures a list of images to remove from the device in order to
    clean up flash by comparing images in flash with running image
    and target image. Target image is specified as 'primary_image'
    in nornir inventory files
    """
    images_in_flash = task.host['images_in_flash']
    running_image = task.host['running_image']
    primary_image = task.host['primary_image']
    images_to_remove = []
    for image in images_in_flash:
        if image != primary_image and image != running_image:
            images_to_remove.append(image)
    task.host['images_to_remove'] = images_to_remove

@nornsible_task
def remove_old_images(task):
    """
    Purges old images from flash on device
    """
    images_to_remove = task.host['images_to_remove']
    for image in images_to_remove:
        command = f'delete flash:/{image}'
        task.run(
            task=networking.netmiko_send_command, 
            command_string=command, 
            **{'expect_string': f'Delete filename'}
        )
        task.run(
            task=networking.netmiko_send_command, 
            command_string='\n', 
            **{'expect_string': '[confirm]'}
        )
        task.run(task=networking.netmiko_send_command, command_string='\n')

@nornsible_task
def copy_primary_image(task):
    """
    Copies target image to device
    """
    primary_image = task.host['primary_image']
    source_file = f'../images/{primary_image}'
    dest_file = primary_image
    task.run(
        task=networking.netmiko_file_transfer, 
        source_file=source_file, 
        dest_file=dest_file
    )

@nornsible_task
def set_boot_vars(task):
    """
    Set's boot vars on device. Primary image is preferred, current
    running image is used as a backup. If primary image and current running image
    are the same, only the primary image is set in the boot vars
    """
    primary_image = task.host['primary_image']
    secondary_image = task.host['running_image']
    if primary_image == secondary_image:
        commands = [
            'default boot system',
            f'boot system flash:/{primary_image}',
        ]
    else:
        commands = [
        'default boot system',
        f'boot system flash:/{primary_image}',
        f'boot system flash:/{secondary_image}',
    ]
    task.run(task=networking.netmiko_send_config, config_commands=commands)
    task.run(task=networking.netmiko_save_config)

@nornsible_task
def verify(task):
    """
    Verifies the device is ready for reboot and assigns a nornir device attribute
    which includes messages about device readiness to be parsed and printed by 
    custom 'print_results' function
    """
    primary_image = task.host['primary_image']
    secondary_image = task.host['running_image']

    # Verify Images exist in Flash
    results_obj = []
    result = task.run(
        task=networking.netmiko_send_command, 
        command_string=f'dir flash:/{primary_image}'
        )
    if primary_image in result[0].result:
        results_obj.append({
            'msg': 'PRIMARY IMAGE IN FLASH',
            'color': 'green',
        }) 
    else:
        results_obj.append({
            'msg': '***** WARNING ***** PRIMARY IMAGE NOT IN FLASH',
            'color': 'red',
        })
    result = task.run(
        task=networking.netmiko_send_command, 
        command_string=f'dir flash:/{secondary_image}'
        )
    if secondary_image in result[0].result:
        results_obj.append({
            'msg': 'SECONDARY IMAGE IN FLASH',
            'color': 'green',
        }) 
    else:
        results_obj.append({
            'msg': '***** WARNING ***** SECONDARY IMAGE NOT IN FLASH',
            'color': 'red',
        }) 

    # Verify Boot Vars Are Set Correctly
    result = task.run(
        task=networking.netmiko_send_command, 
        command_string='show run | i boot system'
        )
    result = result[0].result.splitlines()
    if len(result) == 2:
        if primary_image in result[0]:
            results_obj.append({
                'msg': 'IMAGE BOOT ORDER SET CORRECTLY',
                'color': 'green',
            }) 
        else:
            results_obj.append({
                'msg': '***** WARNING ***** IMAGE BOOT ORDER NOT SET CORRECTLY',
                'color': 'red',
            })
    elif len(result) == 1:
        if primary_image in result[0]:
            results_obj.append({
                'msg': 'DEVICE ALREADY ON TARGET VERSION, NO NEED TO UPGRADE',
                'color': 'yellow',
            }) 
        else:
            results_obj.append({
                'msg': '***** WARNING ***** IMAGE BOOT ORDER NOT SET CORRECTLY',
                'color': 'red',
            })
    else:
        results_obj.append({
            'msg': '***** WARNING ***** WRONG NUMBER OF IMAGES IN BOOT CONFIGURATION',
            'color': 'red',
        }) 
    
    # Write Config
    result = task.run(task=networking.netmiko_save_config)
    if result[0].failed == False:
        results_obj.append({
            'msg': f'CONFIG SAVED, {task.host.name} READY FOR REBOOT',
            'color': 'green',
        }) 
    else:
        results_obj.append({
            'msg': '***** WARNING ***** CONFIG NOT SAVED, DEVICE NOT READY FOR REBOOT',
            'color': 'red',
        }) 

    # Assign results object to task variable
    task.host['script_results'] = results_obj

@nornsible_task
def print_results(task, num_workers=1):
    """
    Print results object procured by 'verify' task
    """
    print(colored(f'\n{task.host.name}: ', 'blue'))
    print(colored('-' * 20, 'blue'))
    for result in task.host['script_results']:
        print(colored(result['msg'], result['color']))

def main():
    nr = InitNornir(config_file=NORNIR_CONFIG_FILE)
    nr = InitNornsible(nr)
    nr.run(task=get_images_in_flash)
    nr.run(task=get_running_image)
    nr.run(task=get_images_to_remove)
    nr.run(task=remove_old_images)
    nr.run(task=copy_primary_image)
    nr.run(task=set_boot_vars)
    nr.run(task=verify)
    nr.run(task=print_results, num_workers=1)

if __name__ == "__main__":
    main()
