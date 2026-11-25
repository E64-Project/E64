/*
 * attach.c - File system attach management.
 *
 * Written by
 *  Andreas Boose <viceteam@t-online.de>
 *
 * This file is part of VICE, the Versatile Commodore Emulator.
 * See README for copyright notice.
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
 *  02111-1307  USA.
 *
 */

#include "vice.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "attach.h"
#include "cmdline.h"
#include "diskimage.h"
#include "driveimage.h"
#include "drive-check.h"
#include "iecdrive.h"
#include "drivetypes.h"
#include "fsdevice.h"
#include "fliplist.h"
#include "lib.h"
#include "log.h"
#include "machine-bus.h"
#include "machine-drive.h"
#include "network.h"
#include "resources.h"
#include "serial.h"
#include "types.h"
#include "uiapi.h"
#include "vdrive-bam.h"
#include "vdrive-iec.h"
#include "vdrive.h"
#include "vice-event.h"
#include "p64.h"

/* #define DEBUG_ATTACH */

#ifdef DEBUG_ATTACH
#define DBG(x)  printf x
#else
#define DBG(x)
#endif

typedef struct {
    serial_t *serial;
    vdrive_t *vdrive;
} file_system_t;

static file_system_t file_system[4];

static log_t attach_log = LOG_DEFAULT;

static int attach_device_readonly_enabled[4];
static int file_system_device_enabled[4];

/* Persisted by VICE resources_save(), including profile-specific vice.ini. */
static int auto_drive_type[4];

static int set_auto_drive_type(int val, void *param)
{
    unsigned int unit = vice_ptr_to_uint(param);
    auto_drive_type[unit - 8] = val ? 1 : 0;
    return 0;
}

static int set_attach_device_readonly(int val, void *param);
static int set_file_system_device(int val, void *param);

static void detach_disk_image(disk_image_t *image, vdrive_t *floppy,
                              unsigned int unit);
static void detach_disk_image_and_free(disk_image_t *image, vdrive_t *floppy,
                                       unsigned int unit);
static int attach_disk_image(disk_image_t **imgptr, vdrive_t *floppy,
                             const char *filename, unsigned int unit,
                             int devicetype);

static const resource_int_t resources_int[] = {
    { "Drive8AutoType", 1, RES_EVENT_SAME, (resource_value_t)1,
      &auto_drive_type[0], set_auto_drive_type, (void *)8 },
    { "Drive9AutoType", 1, RES_EVENT_SAME, (resource_value_t)1,
      &auto_drive_type[1], set_auto_drive_type, (void *)9 },
    { "Drive10AutoType", 1, RES_EVENT_SAME, (resource_value_t)1,
      &auto_drive_type[2], set_auto_drive_type, (void *)10 },
    { "Drive11AutoType", 1, RES_EVENT_SAME, (resource_value_t)1,
      &auto_drive_type[3], set_auto_drive_type, (void *)11 },
    { "AttachDevice8Readonly", 0, RES_EVENT_SAME, NULL,
      &attach_device_readonly_enabled[0],
      set_attach_device_readonly, (void *)8 },
    { "AttachDevice9Readonly", 0, RES_EVENT_SAME, NULL,
      &attach_device_readonly_enabled[1],
      set_attach_device_readonly, (void *)9 },
    { "AttachDevice10Readonly", 0, RES_EVENT_SAME, NULL,
      &attach_device_readonly_enabled[2],
      set_attach_device_readonly, (void *)10 },
    { "AttachDevice11Readonly", 0, RES_EVENT_SAME, NULL,
      &attach_device_readonly_enabled[3],
      set_attach_device_readonly, (void *)11 },
    { "FileSystemDevice8", ATTACH_DEVICE_FS,
      RES_EVENT_STRICT, (resource_value_t)ATTACH_DEVICE_FS,
      &file_system_device_enabled[0],
      set_file_system_device, (void *)8 },
    { "FileSystemDevice9", ATTACH_DEVICE_NONE,
      RES_EVENT_STRICT, (resource_value_t)ATTACH_DEVICE_NONE,
      &file_system_device_enabled[1],
      set_file_system_device, (void *)9 },
    { "FileSystemDevice10", ATTACH_DEVICE_NONE,
      RES_EVENT_STRICT, (resource_value_t)ATTACH_DEVICE_NONE,
      &file_system_device_enabled[2],
      set_file_system_device, (void *)10 },
    { "FileSystemDevice11", ATTACH_DEVICE_NONE,
      RES_EVENT_STRICT, (resource_value_t)ATTACH_DEVICE_NONE,
      &file_system_device_enabled[3],
      set_file_system_device, (void *)11 },
    RESOURCE_INT_LIST_END
};

int file_system_resources_init(void)
{
    return resources_register_int(resources_int);
}

/* ------------------------------------------------------------------------- */

static const cmdline_option_t cmdline_options[] =
{
    { "-device8", SET_RESOURCE, CMDLINE_ATTRIB_NEED_ARGS,
      NULL, NULL, "FileSystemDevice8", (void *)ATTACH_DEVICE_FS,
      "<Type>", "Set device type for device #8 (0: None, 1: Filesystem, 2: OpenCBM, 3: Block device)" },
    { "-device9", SET_RESOURCE, CMDLINE_ATTRIB_NEED_ARGS,
      NULL, NULL, "FileSystemDevice9", (void *)ATTACH_DEVICE_FS,
      "<Type>", "Set device type for device #9 (0: None, 1: Filesystem, 2: OpenCBM, 3: Block device)" },
    { "-device10", SET_RESOURCE, CMDLINE_ATTRIB_NEED_ARGS,
      NULL, NULL, "FileSystemDevice10", (void *)ATTACH_DEVICE_FS,
      "<Type>", "Set device type for device #10 (0: None, 1: Filesystem, 2: OpenCBM, 3: Block device)" },
    { "-device11", SET_RESOURCE, CMDLINE_ATTRIB_NEED_ARGS,
      NULL, NULL, "FileSystemDevice11", (void *)ATTACH_DEVICE_FS,
      "<Type>", "Set device type for device #11 (0: None, 1: Filesystem, 2: OpenCBM, 3: Block device)" },
    { "-attach8ro", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "AttachDevice8Readonly", (resource_value_t)1,
      NULL, "Attach disk image for drive #8 read only" },
    { "-attach8rw", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "AttachDevice8Readonly", (resource_value_t)0,
      NULL, "Attach disk image for drive #8 read write (if possible)" },
    { "-attach9ro", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "AttachDevice9Readonly", (resource_value_t)1,
      NULL, "Attach disk image for drive #9 read only" },
    { "-attach9rw", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "AttachDevice9Readonly", (resource_value_t)0,
      NULL, "Attach disk image for drive #9 read write (if possible)" },
    { "-attach10ro", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "AttachDevice10Readonly", (resource_value_t)1,
      NULL, "Attach disk image for drive #10 read only" },
    { "-attach10rw", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "AttachDevice10Readonly", (resource_value_t)0,
      NULL, "Attach disk image for drive #10 read write (if possible)" },
    { "-attach11ro", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "AttachDevice11Readonly", (resource_value_t)1,
      NULL, "Attach disk image for drive #11 read only" },
    { "-attach11rw", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "AttachDevice11Readonly", (resource_value_t)0,
      NULL, "Attach disk image for drive #11 read write (if possible)" },
    CMDLINE_LIST_END
};

int file_system_cmdline_options_init(void)
{
    return cmdline_register_options(cmdline_options);
}

/* ------------------------------------------------------------------------- */

static int file_system_set_serial_hooks(unsigned int unit, int fs)
{
    DBG(("file_system_set_serial_hooks dev %d: %s\n", unit, !fs ? "vdrive" : "fsdevice"));

    if (!fs) {
        if (vdrive_iec_attach(unit, "CBM Disk Drive")) {
            log_error(attach_log,
                      "Could not initialize vdrive emulation for device #%i.",
                      unit);
            return -1;
        }
    } else {
        if (fsdevice_attach(unit, "FS Drive")) {
            log_error(attach_log,
                      "Could not initialize FS drive for device #%i.",
                      unit);
            return -1;
        }
    }
    return 0;
}

void file_system_init(void)
{
    unsigned int i;

    attach_log = log_open("Attach");

    for (i = 0; i < 8; i++) {
        serial_device_type_set(SERIAL_DEVICE_VIRT, i);
    }

    for (i = 0; i < 4; i++) {
        file_system[i].serial = serial_device_get(i + 8);
        file_system[i].vdrive = lib_calloc(1, sizeof(vdrive_t));
        switch (file_system_device_enabled[i]) {
            case ATTACH_DEVICE_NONE:
                vdrive_device_setup(file_system[i].vdrive, i + 8);
                serial_device_type_set(SERIAL_DEVICE_NONE, i + 8);
                break;
            case ATTACH_DEVICE_FS:
                vdrive_device_setup(file_system[i].vdrive, i + 8);
                serial_device_type_set(SERIAL_DEVICE_FS, i + 8);
                break;
            case ATTACH_DEVICE_REAL:
                vdrive_device_setup(file_system[i].vdrive, i + 8);
                serial_device_type_set(SERIAL_DEVICE_REAL, i + 8);
                break;
            case ATTACH_DEVICE_RAW:
                vdrive_device_setup(file_system[i].vdrive, i + 8);
                serial_device_type_set(SERIAL_DEVICE_RAW, i + 8);
                break;
        }
        file_system_set_serial_hooks(i + 8, file_system_device_enabled[i]);
    }
}

void file_system_shutdown(void)
{
    unsigned int i;

    for (i = 0; i < 4; i++) {
        vdrive_device_shutdown(file_system[i].vdrive);
        lib_free(file_system[i].vdrive);
        machine_bus_device_detach(i + 8); /* free memory allocated by file_system_set_serial_hooks() */
    }
}

struct vdrive_s *file_system_get_vdrive(unsigned int unit)
{
    if (unit < 8 || unit > 11) {
        log_error(attach_log, "Wrong unit for vdrive");
        return NULL;
    }

    return file_system[unit - 8].vdrive;
}

const char *file_system_get_disk_name(unsigned int unit)
{
    vdrive_t *vdrive;

    vdrive = file_system_get_vdrive(unit);

    if (vdrive == NULL) {
        return NULL;
    }
    if (vdrive->image == NULL) {
        return NULL;
    }
    if (vdrive->image->device != DISK_IMAGE_DEVICE_FS) {
        return NULL;
    }

    return disk_image_fsimage_name_get(vdrive->image);
}

int file_system_bam_get_disk_id(unsigned int unit, uint8_t *id)
{
    //return vdrive_bam_get_disk_id(unit, id);
    return vdrive_bam_get_disk_id(unit, 0, id); // VDRIVE_EFFORT
}

int file_system_bam_set_disk_id(unsigned int unit, uint8_t *id)
{
    //return vdrive_bam_set_disk_id(unit, id);
    return vdrive_bam_set_disk_id(unit, 0, id); // VDRIVE_EFFORT
}

/* ------------------------------------------------------------------------- */

static int set_attach_device_readonly(int value, void *param)
{
    unsigned int unit = vice_ptr_to_uint(param);
    const char *old_filename;
    char *new_filename;
    int rc;
    int val = value ? 1 : 0;

    /* Do nothing if resource is unchanged. */
    if (attach_device_readonly_enabled[unit - 8] == val) {
        return 0;
    }

    old_filename = file_system_get_disk_name(unit);

    /* If no disk is attached, just changed the resource.  */
    if (old_filename == NULL) {
        attach_device_readonly_enabled[unit - 8] = val;
        return 0;
    }

    /* Old filename will go away after the image is detached.  */
    new_filename = lib_stralloc(old_filename);

    file_system_detach_disk(unit);
    attach_device_readonly_enabled[unit - 8] = val;

    rc = file_system_attach_disk(unit, new_filename);

    lib_free(new_filename);

    return rc;
}

/* ------------------------------------------------------------------------- */

static int set_file_system_device(int val, void *param)
{
    vdrive_t *vdrive;
    unsigned int unit = vice_ptr_to_uint(param);
    unsigned int idx;
    int old_device_enabled;

    if ((unit < 8) || (unit > 11)) {
        DBG(("set_file_system_device invalid dev #%d\n", unit));
        return -1;
    }
    idx = unit - 8;
    old_device_enabled = file_system_device_enabled[idx];

    vdrive = file_system_get_vdrive(unit);

    DBG(("set_file_system_device dev #%d old dev:%d new dev:%d\n", unit, old_device_enabled, val));

    switch (val) {
        case ATTACH_DEVICE_NONE:
            if (old_device_enabled == ATTACH_DEVICE_REAL) {
                serial_realdevice_disable();
            }
            if (old_device_enabled == ATTACH_DEVICE_RAW) {
                detach_disk_image(vdrive->image, vdrive, unit);
            }

            if (vdrive != NULL && vdrive->image == NULL) {
                vdrive_device_setup(vdrive, unit);
                serial_device_type_set(SERIAL_DEVICE_NONE, unit);
                file_system_set_serial_hooks(unit, 0);
            }
            break;
        case ATTACH_DEVICE_VIRT:
            if (old_device_enabled == ATTACH_DEVICE_REAL) {
                serial_realdevice_disable();
            }
            if (old_device_enabled == ATTACH_DEVICE_RAW) {
                detach_disk_image(vdrive->image, vdrive, unit);
            }

            if (vdrive != NULL && vdrive->image == NULL) {
                vdrive_device_setup(vdrive, unit);
                serial_device_type_set(SERIAL_DEVICE_VIRT, unit);
                file_system_set_serial_hooks(unit, 0);
            }
            break;
        case ATTACH_DEVICE_FS:
            if (old_device_enabled == ATTACH_DEVICE_REAL) {
                serial_realdevice_disable();
            }
            if (old_device_enabled == ATTACH_DEVICE_RAW) {
                detach_disk_image(vdrive->image, vdrive, unit);
            }

            if (vdrive != NULL && vdrive->image != NULL) {
                detach_disk_image_and_free(vdrive->image, vdrive, unit);
                ui_display_drive_current_image(idx, "");
            }
            if (vdrive != NULL && vdrive->image == NULL) {
                vdrive_device_setup(vdrive, unit);
                serial_device_type_set(SERIAL_DEVICE_FS, unit);
                file_system_set_serial_hooks(unit, 1);
            }
            break;
#ifdef HAVE_OPENCBM
        case ATTACH_DEVICE_REAL:
            if (old_device_enabled == ATTACH_DEVICE_RAW) {
                detach_disk_image(vdrive->image, vdrive, unit);
            }
            if (serial_realdevice_enable() < 0) {
                log_warning(attach_log, "Falling back to fs device.");
                return set_file_system_device(ATTACH_DEVICE_FS, param);
            }
            if (vdrive != NULL && vdrive->image != NULL) {
                detach_disk_image_and_free(vdrive->image, vdrive, unit);
                ui_display_drive_current_image(idx, "");
                vdrive_device_setup(vdrive, unit);
            }
            serial_device_type_set(SERIAL_DEVICE_REAL, unit);
            break;
#endif
#ifdef HAVE_RAWDRIVE
        case ATTACH_DEVICE_RAW:
            if (old_device_enabled == ATTACH_DEVICE_REAL) {
                serial_realdevice_disable();
            }
            if (vdrive != NULL && vdrive->image != NULL) {
                detach_disk_image_and_free(vdrive->image, vdrive, unit);
                ui_display_drive_current_image(idx, "");
                vdrive_device_setup(vdrive, unit);
            }
            attach_disk_image(&(vdrive->image), vdrive, "DUMMY", unit,
                              ATTACH_DEVICE_RAW);
            file_system_set_serial_hooks(unit, 0);
            serial_device_type_set(SERIAL_DEVICE_RAW, unit);
            break;
#endif
        default:
            return -1;
    }

    file_system_device_enabled[idx] = val;

    return 0;
}

/* ------------------------------------------------------------------------- */

static void detach_disk_image(disk_image_t *image, vdrive_t *floppy,
                              unsigned int unit)
{
    switch (unit) {
        case 8:
            machine_drive_image_detach(image, 8);
            drive_image_detach(image, 8);
            vdrive_detach_image(image, 8, 0, floppy); // VDRIVE_EFFORT
            break;
        case 9:
            machine_drive_image_detach(image, 9);
            drive_image_detach(image, 9);
            vdrive_detach_image(image, 9, 0, floppy); // VDRIVE_EFFORT
            break;
        case 10:
            machine_drive_image_detach(image, 10);
            drive_image_detach(image, 10);
            vdrive_detach_image(image, 10, 0, floppy); // VDRIVE_EFFORT
            break;
        case 11:
            machine_drive_image_detach(image, 11);
            drive_image_detach(image, 11);
            vdrive_detach_image(image, 11, 0, floppy); // VDRIVE_EFFORT
            break;
    }
    disk_image_close(image);

#if 0
    if (image != NULL) {
        P64ImageDestroy((PP64Image)image->p64);
        lib_free(image->p64);
    }
#endif
    disk_image_media_destroy(image);
}

static void detach_disk_image_and_free(disk_image_t *image, vdrive_t *floppy,
                                       unsigned int unit)
{
    disk_image_t *oldimg;

    if (floppy == NULL || floppy->image == NULL) {
        return;
    }

    oldimg = floppy->image;

    detach_disk_image(image, floppy, unit);

    if ((image != NULL) && (image == oldimg)) {
        disk_image_destroy(image);
    }
}

static int attach_disk_image(disk_image_t **imgptr, vdrive_t *floppy,
                             const char *filename, unsigned int unit,
                             int devicetype)
{
    disk_image_t *image;
    disk_image_t new_image;
    int err = -1;
    int image_opened = 0;
    int selected_type = DRIVE_TYPE_NONE;

    if (filename == NULL) {
        log_error(attach_log, "No name, cannot attach floppy image.");
        return -1;
    }

    new_image.gcr = NULL;
    new_image.p64 = lib_calloc(1, sizeof(TP64Image));
    new_image.read_only = (unsigned int)attach_device_readonly_enabled[unit - 8];

    switch (devicetype) {
        case ATTACH_DEVICE_NONE:
        case ATTACH_DEVICE_VIRT:
        case ATTACH_DEVICE_FS:
            new_image.device = DISK_IMAGE_DEVICE_FS;
            break;
        case ATTACH_DEVICE_RAW:
            new_image.device = DISK_IMAGE_DEVICE_RAW;
            break;
    }

    disk_image_media_create(&new_image);

    switch (devicetype) {
        case ATTACH_DEVICE_NONE:
        case ATTACH_DEVICE_VIRT:
        case ATTACH_DEVICE_FS:
            disk_image_fsimage_name_set(&new_image, filename);
            break;
        case ATTACH_DEVICE_RAW:
            disk_image_rawimage_driver_name_set(&new_image);
            break;
    }

    if (disk_image_open(&new_image) < 0) {
        goto open_error;
    }

    image_opened = 1;

    if (new_image.type == DISK_IMAGE_TYPE_DHD) {
        int drive_type;
        int true_emulation;

        resources_get_int_sprintf("Drive%iType", &drive_type, unit);
        resources_get_int_sprintf("Drive%iTrueEmulation", &true_emulation, unit);
        log_message(attach_log, "CMDHD: Drive %u before attach: type=%d TDE=%d.",
                    unit, drive_type, true_emulation);

        if (machine_drive_rom_check_loaded(DISK_IMAGE_TYPE_DHD) < 0) {
            log_error(attach_log,
                      "CMDHD: Cannot attach `%s': no CMDHD boot ROM is configured.",
                      filename);
            goto open_error;
        }

        if (resources_set_int_sprintf("Drive%iType", DRIVE_TYPE_CMDHD, unit) < 0
            || resources_set_int_sprintf("Drive%iTrueEmulation", 1, unit) < 0) {
            log_error(attach_log,
                      "CMDHD: Cannot configure drive %u for CMDHD true-drive emulation.",
                      unit);
            goto open_error;
        }

        resources_get_int_sprintf("Drive%iType", &drive_type, unit);
        resources_get_int_sprintf("Drive%iTrueEmulation", &true_emulation, unit);
        log_message(attach_log, "CMDHD: Drive %u prepared: type=%d TDE=%d.",
                    unit, drive_type, true_emulation);
    } else {
        /* Choose a suitable drive for a recognized floppy image on the
           requested unit (8-11). Do not change an already compatible model.
           CMD HD's separate handling above remains unchanged. */
        int current_type = DRIVE_TYPE_NONE;
        int preferred_type = DRIVE_TYPE_NONE;
        int compatible = 0;

        if (resources_get_int_sprintf("Drive%iType", &current_type, unit) < 0) {
            goto open_error;
        }

        switch (new_image.type) {
            case DISK_IMAGE_TYPE_D64:
            case DISK_IMAGE_TYPE_G64:
            case DISK_IMAGE_TYPE_P64:
                preferred_type = DRIVE_TYPE_1541II;
                break;
            case DISK_IMAGE_TYPE_D71:
            case DISK_IMAGE_TYPE_G71:
                preferred_type = DRIVE_TYPE_1571;
                break;
            case DISK_IMAGE_TYPE_D81:
                preferred_type = DRIVE_TYPE_1581;
                break;
            /* Do not auto-select 8250 for D82: this R4 setup has no
               8250 drive ROM. An existing manual setting is retained. */
            case DISK_IMAGE_TYPE_D1M:
            case DISK_IMAGE_TYPE_D2M:
                /* DD and HD floppy images work with FD2000 or FD4000. */
                preferred_type = DRIVE_TYPE_2000;
                break;
            case DISK_IMAGE_TYPE_D4M:
                /* ED floppy images require an FD4000. */
                preferred_type = DRIVE_TYPE_4000;
                break;
            default:
                /* Other formats keep their explicitly configured model. */
                break;
        }

        compatible = drive_image_check_format(new_image.type, current_type) == 0;
        if (auto_drive_type[unit - 8]
            && preferred_type != DRIVE_TYPE_NONE && !compatible) {
            if (machine_drive_rom_check_loaded(preferred_type) < 0
                || !drive_check_bus(preferred_type, iec_available_busses())) {
                log_error(attach_log,
                          "Cannot select drive type %d for image `%s' on unit %u.",
                          preferred_type, filename, unit);
                goto open_error;
            }
            selected_type = preferred_type;
        }
    }

    /* Reject incompatible true-drive mounts before disturbing the old disk.
       Virtual-device mode deliberately retains its existing format support. */
    if (new_image.type != DISK_IMAGE_TYPE_DHD) {
        int effective_type, true_emulation;
        resources_get_int_sprintf("Drive%iType", &effective_type, unit);
        resources_get_int_sprintf("Drive%iTrueEmulation", &true_emulation, unit);
        if (selected_type != DRIVE_TYPE_NONE) {
            effective_type = selected_type;
        }
        if (true_emulation
            && (drive_image_check_format(new_image.type, effective_type) < 0
                || machine_drive_rom_check_loaded(effective_type) < 0)) {
            log_error(attach_log, "Drive %u cannot use image `%s' with model %d.",
                      unit, filename, effective_type);
            goto open_error;
        }
    }

    detach_disk_image_and_free(*imgptr, floppy, unit);
    /* Setup clears the image pointer: only do it after closing the old disk. */
    vdrive_device_setup(floppy, unit);
    serial_device_type_set(SERIAL_DEVICE_VIRT, unit);

    if (selected_type != DRIVE_TYPE_NONE) {
        int effective_type;
        if (resources_set_int_sprintf("Drive%iType", selected_type, unit) < 0) {
            goto open_error;
        }
        resources_get_int_sprintf("Drive%iType", &effective_type, unit);
        if (effective_type != selected_type) {
            log_error(attach_log, "Drive %u did not accept model %d.", unit, selected_type);
            goto open_error;
        }
        log_message(attach_log, "Drive %u: selected model %d for image `%s'.",
                    unit, selected_type, filename);
    }

    *imgptr = disk_image_create();
    image = *imgptr;

    memcpy(image, &new_image, sizeof(disk_image_t));
    /* free the P64 stuff, fixes the leak in src/attach.c, reported when
     * using --enable-debug */
    lib_free(new_image.p64);

    switch (unit) {
        case 8:
        case 9:
        case 10:
        case 11:
            {
                int drive_err = drive_image_attach(image, unit);
                int virtual_err = vdrive_attach_image(image, unit, 0, floppy);
                int machine_err = machine_drive_image_attach(image, unit);
                int true_emulation;
                err = drive_err & virtual_err & machine_err;
                resources_get_int_sprintf("Drive%iTrueEmulation", &true_emulation, unit);
                /* A virtual attachment must not hide a failed physical backend
                   when true-drive emulation was explicitly requested. */
                if (image->type != DISK_IMAGE_TYPE_DHD
                    && (virtual_err < 0 || (true_emulation
                        && drive_err < 0 && machine_err < 0))) {
                    err = -1;
                }
            }
            break;
    }
    if (!err && image->type == DISK_IMAGE_TYPE_DHD) {
        machine_bus_status_truedrive_set(unit, 1);
        log_message(attach_log,
                    "CMDHD: Drive %u true-drive serial traps enabled.", unit);
    }
    if (err) {
        /* The virtual backend may already have cleared floppy->image. */
        detach_disk_image(image, floppy, unit);
        disk_image_destroy(image);
        *imgptr = NULL;
    }
    return err;

open_error:
        if (image_opened) {
            disk_image_close(&new_image);
        }
        P64ImageDestroy((PP64Image) new_image.p64);
        lib_free(new_image.p64);
        disk_image_media_destroy(&new_image);
        return -1;
}

/* ------------------------------------------------------------------------- */

static int file_system_attach_disk_internal(unsigned int unit,
                                            const char *filename)
{
    vdrive_t *vdrive;

    vdrive = file_system_get_vdrive(unit);

    /* Save configuration for rollback; the candidate is opened and checked
       before attach_disk_image commits the replacement. */
    const char *previous_name = vdrive->image != NULL
        ? disk_image_name_get(vdrive->image) : NULL;
    char *old_name = previous_name != NULL ? lib_stralloc(previous_name) : NULL;
    int old_type[4], old_tde, i;
    unsigned int old_serial_type = serial_device_type_get(unit);
    for (i = 0; i < 4; ++i) {
        resources_get_int_sprintf("Drive%iType", &old_type[i], i + 8);
    }
    resources_get_int_sprintf("Drive%iTrueEmulation", &old_tde, unit);

    if (attach_disk_image(&(vdrive->image), vdrive, filename, unit,
                          file_system_device_enabled[unit - 8]) < 0) {
        for (i = 0; i < 4; ++i) {
            int current_type;
            resources_get_int_sprintf("Drive%iType", &current_type, i + 8);
            if (current_type != old_type[i]) {
                resources_set_int_sprintf("Drive%iType", old_type[i], i + 8);
            }
        }
        resources_set_int_sprintf("Drive%iTrueEmulation", old_tde, unit);
        if (old_name != NULL && vdrive->image == NULL) {
            int saved_auto = auto_drive_type[unit - 8];
            auto_drive_type[unit - 8] = 0;
            if (attach_disk_image(&(vdrive->image), vdrive, old_name, unit,
                                  file_system_device_enabled[unit - 8]) < 0) {
                log_error(attach_log, "Drive %u: could not restore previous disk `%s'.",
                          unit, old_name);
                ui_display_drive_current_image(unit - 8, "");
            } else {
                file_system_set_serial_hooks(unit, 0);
            }
            auto_drive_type[unit - 8] = saved_auto;
        }
        if (old_name == NULL && serial_device_type_get(unit) != old_serial_type) {
            serial_device_type_set(old_serial_type, unit);
            file_system_set_serial_hooks(unit,
                file_system_device_enabled[unit - 8] == ATTACH_DEVICE_FS);
        }
        lib_free(old_name);
        return -1;
    } else {
        file_system_set_serial_hooks(unit, 0);
        fliplist_set_current(unit, filename);
        ui_display_drive_current_image(unit - 8, filename);
    }

    lib_free(old_name);
    event_record_attach_image(unit, filename, vdrive->image->read_only);

    return 0;
}

int file_system_attach_disk(unsigned int unit, const char *filename)
{
    if (event_playback_active()) {
        return -1;
    }

    if (network_connected()) {
        network_attach_image(unit, filename);
        return 0;
    }

    return file_system_attach_disk_internal(unit, filename);
}

static void file_system_detach_disk_single(unsigned int unit)
{
    vdrive_t *vdrive;

    vdrive = file_system_get_vdrive(unit);
    if (vdrive != NULL && vdrive->image != NULL) {
        detach_disk_image_and_free(vdrive->image, vdrive, (unsigned int)unit);
        ui_display_drive_current_image(unit - 8, "");
    }

    set_file_system_device(file_system_device_enabled[unit - 8], uint_to_void_ptr(unit));
}

static void file_system_detach_disk_internal(int unit)
{
    char event_data[2];

    if (unit < 0) {
        unsigned int i;

        for (i = 8; i <= 11; i++) {
            file_system_detach_disk_single(i);
        }
    } else {
        if (unit >= 8 && unit <= 11) {
            file_system_detach_disk_single((unsigned int)unit);
        } else {
            log_error(attach_log, "Cannot detach unit %i.", unit);
        }
    }

    event_data[0] = (char)unit;
    event_data[1] = 0;

    event_record(EVENT_ATTACHDISK, (void *)event_data, 2);
}

void file_system_detach_disk(int unit)
{
    char event_data[2];

    if (event_playback_active()) {
        return;
    }

    event_data[0] = (char)unit;
    event_data[1] = 0;

    if (network_connected()) {
        network_event_record(EVENT_ATTACHDISK, (void *)event_data, 2);
        return;
    }

    file_system_detach_disk_internal(unit);
}

void file_system_detach_disk_shutdown(void)
{
    vdrive_t *vdrive;
    unsigned int i;

    for (i = 0; i <= 3; i++) {
        vdrive = file_system_get_vdrive(i + 8);
        if (vdrive != NULL) {
            if (file_system_device_enabled[i] == ATTACH_DEVICE_REAL) {
                serial_realdevice_disable();
            } else {
                detach_disk_image_and_free(vdrive->image, vdrive, i + 8);
            }
        }
    }
}

void file_system_event_playback(unsigned int unit, const char *filename)
{
    if (filename == NULL || filename[0] == 0) {
        file_system_detach_disk_internal(unit);
    } else {
        file_system_attach_disk_internal(unit, filename);
    }
}
