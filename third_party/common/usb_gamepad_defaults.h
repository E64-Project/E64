#ifndef BMC64_USB_GAMEPAD_DEFAULTS_H
#define BMC64_USB_GAMEPAD_DEFAULTS_H

#define USB_GAMEPAD_DEFAULT_CONFIG_NONE 0
#define USB_GAMEPAD_DEFAULT_CONFIG_XBOX360 1
#define USB_GAMEPAD_DEFAULT_CONFIG_8BITDO_M30_2_4G 2

struct usb_gamepad_button_default {
  unsigned button;
  int assignment;
};

struct usb_gamepad_default_config {
  unsigned id;
  const char *display_name;
  int direction_mode;
  int x_axis;
  int y_axis;
  float x_threshold;
  float y_threshold;
  const struct usb_gamepad_button_default *button_defaults;
  unsigned button_default_count;
};

void emu_set_usb_gamepad_mapping_config(int device, unsigned config);
void emu_set_usb_gamepad_display_name(int device, const char *display_name);

unsigned usb_gamepad_default_config_for_vendor(const char *vendor);
const struct usb_gamepad_default_config *usb_gamepad_default_config_for_device(
    int device);
const char *usb_gamepad_default_config_display_name_for_device(int device);
void usb_gamepad_reset_to_defaults(int device);

#endif
