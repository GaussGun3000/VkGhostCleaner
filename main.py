import traceback

import PySimpleGUI as sg
from VkUserBot import VkUserBot, read_token
from logger import Logger
"""
TODO:
-timer: make timer (request counter) in the main thread, and transfer API to sub-thread
"""
from vkbottle import VKAPIError


class GUIWindow:
    """Class that defines look and behavior of GUI"""

    def __init__(self):
        sg.theme("DarkAmber")
        self.logger = Logger()
        self.layout = self.layout_template()
        self.layout_name = 'main'
        self.window = sg.Window(title="VKGhostCleaner", layout=self.layout, scaling=1.5, margins=(50, 10))
        self.vk = VkUserBot(self.logger)  # bridge to vk API handler class
        self.logger.log("GUI controller initialized")

    def start_event_loop(self):
        """Start event loop for PySimpleGUI"""
        self.logger.log("Staring the event loop...")
        while True:
            try:
                event, values = self.window.read()
                if event == sg.WIN_CLOSED or event == 'Выход':
                    break
                else:
                    self.event_handler(event, values)
            except VKAPIError as ex:
                tb = traceback.format_exc()
                sg.Print('Данная ошибка может быть связана с VK. Попробуйте ещё раз снова. '
                         'Если ошибка повторится, свяжитесь с разрабочиком, отправив ему этот '
                         f'текст: \n{tb}', keep_on_top=True, wait=True)

                break
            except Exception as ex:
                tb = traceback.format_exc()
                sg.Print('Произошла неизвестная ошибка. Попробуйте перезапустить приложение.'
                         ' Если ошибка повторится, свяжитесь с разработчиком, отправив ему этот '
                         f'текст: \n{tb}', keep_on_top=True, wait=True)
                break
        self.logger.close()
        self.window.close()

    def event_handler(self, event, values):
        """
        :param event: event string provided by sg.window.read()
        :param values: values that can be extracted from input fields

        Handles GUI events from event loop
         """
        vk = self.vk
        window = self.window
        if event == "Поиск неактивных":
            self.switch_layout('search')
        elif event == "🔍":
            self.logger.log(f"searching group {values.get('group input')}")
            group_name = vk.find_group_sync(values.get('group input'))
            group_name = f"Найдена группа: {group_name}" if group_name else "Группа не найдена"
            window.find_element(key='group_name').update(group_name)
        elif event == 'back' or event == 'back1':
            self.switch_layout('main')
        elif event == 'Удаление неактивных':
            self.switch_layout('delete')
        elif event == 'find':
            self.event_find(values)
        elif event == 'Подтверждаю удаление!':
            self.event_delete(values)
        else:
            self.logger.log("Unknown event: " + event)

    def event_find(self, values):
        """Handles 'find' event"""
        window = self.window
        vk = self.vk
        if vk.find_group_sync(values.get('group input')):
            try:
                posts_amount = int(values.get('post input'))
                if posts_amount > 0:
                    try:
                        rps = int(values.get('rps input'))
                        if rps in range(3, 101):
                            inactive = self.vk.find_inactive(posts_amount, window, rps)
                        else:
                            inactive = self.vk.find_inactive(posts_amount, window)
                        message = f"Выявлено неактивных: {len(inactive)}"
                        window.find_element(key='group_name').update(message)
                    except ValueError:
                        inactive = self.vk.find_inactive(posts_amount, window)
                        message = f"Выявлено неактивных: {len(inactive)}"
                        window.find_element(key='group_name').update(message)
                else:
                    warning = "⚠ Во втором окне ввода должно быть положительное число постов!"
                    window.find_element(key='group_name').update(warning)
            except ValueError:
                warning = "⚠ Во втором окне ввода должно быть положительное число постов!"
                window.find_element(key='group_name').update(warning)
            except VKAPIError[15]:
                warning = "⚠ Недостаточно прав доступа токена!"
                window.find_element(key='delete progress').update(warning)
            except VKAPIError[6]:
                warning = "⚠ Слишком высокий RPS!"
                window.find_element(key='delete progress').update(warning)
        else:
            warning = "⚠ Группа не найдена! Проверьте введённое значение"
            window.find_element(key='group_name').update(warning)

    def event_delete(self, values):
        window = self.window
        vk = self.vk
        if vk.inactive:
            try:
                rps = int(values.get('rps input'))
                if rps in range(3, 101):
                    result = self.vk.delete(window, rps)
                else:
                    result = self.vk.delete(window)
                message = f"Удалено: {result}"
                window.find_element(key='delete progress').update(message)
            except ValueError:
                result = self.vk.delete(window)
                message = f"Удалено: {result}"
                window.find_element(key='delete progress').update(message)
            except VKAPIError[15]:
                warning = "⚠ Недостаточно прав доступа токена!"
                window.find_element(key='delete progress').update(warning)
            except VKAPIError[6]:
                warning = "⚠ Слишком высокий RPS!"
                window.find_element(key='delete progress').update(warning)
        else:
            warning = "⚠ Сначала необходимо произвести поиск!"
            window.find_element(key='delete progress').update(warning)

    def switch_layout(self, layout_name: str):
        """Show layout 'layout_name' (one of main, search, delete) and hide previous"""
        if layout_name == 'main':
            self.window['COL1'].update(visible=True)
            if self.layout_name == 'search':
                self.window['COL2'].update(visible=False)
            elif self.layout_name == 'delete':
                self.window['COL3'].update(visible=False)
            else:
                raise ValueError(f"switch_layout() exception: illegal Window.layout_name value '{self.layout_name}'")
            self.layout_name = 'main'
        elif layout_name == 'search':
            self.layout_name = 'search'
            self.window['COL2'].update(visible=True)
            self.window['COL1'].update(visible=False)
        elif layout_name == 'delete':
            self.layout_name = 'delete'
            self.window['COL3'].update(visible=True)
            self.window['COL1'].update(visible=False)
        elif layout_name == 'key':
            self.window['COL4'].update(visible=True)
            self.window['COL1'].update(visible=False)
        else:
            raise ValueError(f"switch_layout() exception: Illegal argument {layout_name}")

    @staticmethod
    def layout_template():
        """Return the layout template"""
        token = read_token()
        token_text = "" if token else "\n⚠ файл token.txt пуст"
        header = [sg.Text(text=f'Главное Меню{token_text}', justification='center', pad=(0, (5, 30)),
                          font=('Arial', 16))]
        column_main = [header,
                       [sg.Button('Поиск неактивных', size=(25, 2), pad=(0, (10, 10)))],
                       [sg.Button('Удаление неактивных', size=(25, 2), pad=(0, (10, 10)))],
                       [sg.Button('Выход', size=(25, 2), pad=(0, (10, 10)))]]
        column_search = [[sg.Text(text='Поиск неактивных', justification='center', font=('Arial', 14))],
                         [sg.InputText(default_text="Введите ID гурппы", size=(40, 2), key='group input'),
                          sg.Button('🔍')],
                         [sg.Text(key='group_name', pad=(0, (10, 10)), size=(40, 1), justification='center')],
                         [sg.InputText(default_text="Укажите число постов", size=(40, 2), key='post input',
                                       pad=((0, 40), (10, 10)))],
                         [sg.Text('Расширенные настройки:', pad=(0, (10, 10)))],
                         [sg.Text('RPS', tooltip='См. инструкцию. Не стоит менять, если не понятно, что это!'),
                          sg.InputText(default_text="3", size=(10, 2), key='rps input', pad=(0, (10, 10)))],
                         [sg.Button('Поиск', key='find', size=(10, 1), pad=(0, (10, 10)))],
                         [sg.Button('Назад', key='back', size=(10, 1), pad=(0, (10, 10)))]]
        warning_text = '⚠ Внимание! Данное действие невозможно будет отменить. Рекомендуется посмотреть файл inactive.xlsx, ' \
                       'чтобы убедится, что список примерно соотвествует ожиданиям и был составлен верно. Сохраните копию файла' \
                       ' перед тем, как продолжить. Перед выполнением операции необходимо произвести поиск неактивных ' \
                       'в одной сессии (до следующего закрытия окна)'
        column_delete = [[sg.Text(text='Удаление неактивных', justification='center', font=('Arial', 14))],
                         [sg.Text(text=warning_text, font=('Arial', 10, 'normal'), size=(60, 6))],
                         [sg.Text('Расширенные настройки:', pad=(0, (10, 10)))],
                         [sg.Text('RPS', tooltip='См. инструкцию. Не стоит менять, если не понятно, что это!'),
                          sg.InputText(default_text="3", size=(10, 2), key='rps delete', pad=(0, (10, 10)))],
                         [sg.Text('', pad=(0, (15, 10)), key='delete progress')],
                         [sg.Button('Подтверждаю удаление!', pad=(0, (10, 30)))],
                         [sg.Button('Назад', key='back1', size=(10, 1))]]
        column_key = [[sg.Text(text='Отсутствует ключ активации!', justification='center', font=('Arial', 14))],
                      [sg.Text(text='Проверьте наличие файла key.txt', justification='center', pad=(0, (10, 10)))]]
        layout = [[sg.Column(column_main, key='COL1', element_justification='center'),
                   sg.Column(column_search, key='COL2', visible=False, element_justification='center'),
                   sg.Column(column_key, key='COL4', visible=False, element_justification='center'),
                   sg.Column(column_delete, key='COL3', visible=False, element_justification='center')]]
        return layout


def gui_window():
    window = GUIWindow()
    window.start_event_loop()


if __name__ == '__main__':
    gui_window()
