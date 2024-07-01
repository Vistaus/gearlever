import gi
import logging

from .lib.costants import FETCH_UPDATES_ARG
from .models.Models import InternalError
from .lib.utils import get_gsettings, portal
from .State import state
from dbus import Array as DBusArray

gi.require_version('Gtk', '4.0')

from gi.repository import Adw, Gtk, Gio, GLib  # noqa

class Preferences(Adw.PreferencesWindow):
    def __init__(self, **kwargs) :
        super().__init__(**kwargs)

        self.settings = get_gsettings()
 
        # page 1
        page1 = Adw.PreferencesPage()

        # general group
        general_preference_group = Adw.PreferencesGroup(name=_('General'))


        # default_location
        self.default_location_row = Adw.ActionRow(
            title=_('AppImage default location'),
            subtitle=self.settings.get_string('appimages-default-folder')
        )

        pick_default_localtion_btn = Gtk.Button(icon_name='gearlever-file-manager-symbolic', valign=Gtk.Align.CENTER)
        pick_default_localtion_btn.connect('clicked', self.on_default_localtion_btn_clicked)
        self.default_location_row.add_suffix(pick_default_localtion_btn)

        files_outside_folder_switch = self.create_boolean_settings_entry(
            _('Show integrated AppImages outside the default folder'),
            'manage-files-outside-default-folder',
            _('List AppImages that have been integrated into the system menu but are located outside the default folder')
        )

        general_preference_group.add(self.default_location_row)
        general_preference_group.add(files_outside_folder_switch)

        # updates management group
        updates_management_group = Adw.PreferencesGroup(name=_('Updates management'), title=_('Updates management'))
        autofetch_updates = self.create_boolean_settings_entry(
            _('Check updates in the backgroud'),
            'fetch-updates-in-background',
            _('Receive a notification when a new update is detected; updates will not be installed automatically')
        )

        updates_management_group.add(autofetch_updates)
        autofetch_updates.connect('notify::active', self.on_background_fetchupdates_changed)

        # file management group
        move_appimages_group = Adw.PreferencesGroup(name=_('File management'), title=_('File management'))
        move_appimages_row = Adw.ActionRow(
            title=_('Move AppImages into the destination folder'),
            subtitle=(_('Reduce disk usage'))
        )

        copy_appimages_row = Adw.ActionRow(
            title=_('Clone AppImages into the destination folder'),
            subtitle=(_('Keep the original file and create a copy in the destination folder'))
        )


        self.move_to_destination_check = Gtk.CheckButton(
            valign=Gtk.Align.CENTER,
            active=self.settings.get_boolean('move-appimage-on-integration')
        )

        self.copy_to_destination_check = Gtk.CheckButton(
            valign=Gtk.Align.CENTER,
            group=self.move_to_destination_check,
            active=(not self.settings.get_boolean('move-appimage-on-integration'))
        )

        move_appimages_row.add_prefix(self.move_to_destination_check)
        copy_appimages_row.add_prefix(self.copy_to_destination_check)

        move_appimages_group.add(move_appimages_row)
        move_appimages_group.add(copy_appimages_row)
        # move_appimages_group.add(exec_as_name_switch)

        self.move_to_destination_check.connect('toggled', self.on_move_appimages_setting_changed)
        self.copy_to_destination_check.connect('toggled', self.on_move_appimages_setting_changed)

        # naming conventions group
        nconvention_group = Adw.PreferencesGroup(name=_('Naming conventions'), title=_('Naming conventions'))
        exec_as_name_switch = self.create_boolean_settings_entry(
            _('Use executable name for integrated terminal apps'),
            'exec-as-name-for-terminal-apps',
            _('If enabled, apps that run in the terminal are renamed as their executable.\nYou would need to add the aforementioned folder to your $PATH manually.\n\nFor example, "golang_x86_64.appimage" will be saved as "go"')
        )

        simple_filename_name_switch = self.create_boolean_settings_entry(
            _('Save appimages files without prefixes'),
            'simple-file-name-for-apps',
            _('When enabled, every appimage will be renamed as a short, lowercase version of their app name, without the "gearlever" prefix.\n\nFor example, "kdenlive-24.02-x86_64.appimage" will be saved as "kdelive.appimage"')
        )

        nconvention_group.add(exec_as_name_switch)
        nconvention_group.add(simple_filename_name_switch)

        # debugging group
        debug_group = Adw.PreferencesGroup(name=_('Debugging'), title=_('Debugging'))
        debug_row = self.create_boolean_settings_entry(
            _('Enable debug logs'),
            'debug-logs',
            _('Increases log verbosity, occupying more disk space and potentially impacting performance.\nRequires a restart.')
        )

        debug_group.add(debug_row)

        page1.add(general_preference_group)
        page1.add(updates_management_group)
        page1.add(move_appimages_group)
        page1.add(nconvention_group)
        page1.add(debug_group)
        self.add(page1)

    def on_select_default_location_response(self, dialog, result):
        try:
            selected_file = dialog.select_folder_finish(result)
        except Exception as e:
            logging.error(str(e))
            return

        if selected_file.query_exists() and selected_file.get_path().startswith(GLib.get_home_dir()):
            self.settings.set_string('appimages-default-folder', selected_file.get_path())
            self.default_location_row.set_subtitle(selected_file.get_path())
            state.set__('appimages-default-folder', selected_file.get_path())
        else:
            raise InternalError(_('The folder must be in your home directory'))

    def on_default_localtion_btn_clicked(self, widget):
        dialog = Gtk.FileDialog(title=_('Select a folder'), modal=True)

        dialog.select_folder(
            parent=self,
            cancellable=None,
            callback=self.on_select_default_location_response
        )

    def on_move_appimages_setting_changed(self, widget):
        self.settings.set_boolean('move-appimage-on-integration', self.move_to_destination_check.get_active())

    def create_boolean_settings_entry(self, label: str, key: str, subtitle: str = None) -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=label, subtitle=subtitle)
        self.settings.bind(key, row, 'active', Gio.SettingsBindFlags.DEFAULT)

        return row
        
    def on_background_fetchupdates_changed(self, *args):
        value: bool = self.settings.get_boolean('fetch-updates-in-background')
        
        inter = portal("org.freedesktop.portal.Background")
        res = inter.RequestBackground('', {
            'reason': 'Gear Lever background updates fetch', 
            'autostart': value, 
            'background': value, 
            'commandline': DBusArray(['gearlever', FETCH_UPDATES_ARG])
        })


