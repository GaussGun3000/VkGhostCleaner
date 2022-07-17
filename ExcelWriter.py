import traceback

import pandas as pd


def dump_users(vk):
    try:
        df = pd.read_excel("inactive_template.xlsx")
        data = vk.collect_users_info()
        for user in data:
            add = pd.DataFrame(
                {
                    'Имя': [user.first_name],
                    'Фамилия': [user.last_name],
                    'Ссылка': [f'https://vk.com/{user.screen_name}'],
                })
            df = pd.concat([df, add], ignore_index=True, axis=0)
        df.to_excel("inactive.xlsx", index=False)
    except Exception as ex:
        print(ex)
        traceback.print_exc()
        return None
