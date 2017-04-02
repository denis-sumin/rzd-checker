# coding=utf-8
import datetime
import sys

import requests
import telegram

from settings import BOT_TOKEN, MY_TELEGRAM_ID

bot = telegram.Bot(token=BOT_TOKEN)
COOKIE = 'JSESSIONID=0000Rzt5E96njjvSmVkq4kNft-Y:17obq8rib'


def get_data(url, data, headers):
    r_rid = requests.post(url, data=data, headers=headers)
    try:
        if r_rid.json()['result'] == 'RID':
            data['rid'] = r_rid.json()['RID']
        else:
            raise RuntimeError('No RID')
    except Exception as e:
        print(e)
        raise

    while True:
        r_data = requests.post(url, data=data, headers=headers)
        try:
            if r_data.json()['result'] == 'OK':
                break
            elif r_data.json()['result'] == 'RID':
                data['rid'] = r_rid.json()['RID']
                continue
            else:
                print('Unexpecred result', r_data.json())
                exit()
        except Exception as e:
            print(e)
            continue

    return r_data.json()


def check_trains(code_from, code_to, date, needed_train, needed_type):
    url = 'https://pass.rzd.ru/timetable/public/ru?layer_id=5827'
    data = {
        'checkSeats': 1,
        'code0': code_from,
        'code1': code_to,
        'dir': 0,
        'dt0': date,
        'tfl': 3,
    }
    headers = {
        'Cookie': COOKIE,
    }

    data = get_data(url, data, headers)
    assert len(data['tp']) == 1

    print(data['tp'][0]['from'], data['tp'][0]['where'], data['tp'][0]['date'])

    trains = data['tp'][0]['list']

    results = list()

    for train in trains:
        if (
                str(needed_train) in train['number'] or
                str(needed_train) in train['number2']
        ):
            print('Запрошенный поезд {} найден'.format(needed_train))
            for car_type in train['cars']:
                if car_type['type'] == needed_type:
                    results.append(train)
    return results


def check_car_and_seat(code_from, code_to, date, train_number,
               needed_car, needed_seat=None):
    data = {
        'dir': 0,
        'seatDetails': 1,
        'code0': code_from,
        'code1': code_to,
        'tnum0': train_number,
        'dt0': date,
        'bEntire': 'false',
    }
    headers = {
        'Cookie': COOKIE,
    }
    url = 'https://pass.rzd.ru/timetable/public/ru?layer_id=5764'
    data = get_data(url, data, headers)
    assert len(data['lst']) == 1
    cars = data['lst'][0]['cars']

    found_car = False
    for car in cars:
        if int(car['cnumber']) == needed_car:
            found_car = True
            print('Найден нужный вагон: {}'.format(needed_car))
            if not needed_seat:
                return
            available_seats = sorted([
                int(s2) for s1 in car['seats']
                for s2 in s1['places'].split(',')])
            if needed_seat in available_seats:
                print('Запрошенное место {} найдено!'.format(needed_seat))
                bot.sendMessage(
                    chat_id=MY_TELEGRAM_ID,
                    text='Запрошенное место {} найдено!'.format(needed_seat))
            else:
                print(
                    'Запрошенное место {} не найдено. Доступны места: {}'
                    .format(needed_seat,
                            ', '.join((str(s) for s in available_seats))))
    if not found_car:
        print('Нужный вагон {} не найден'.format(needed_car))


def main():
    """
    1: code_from
    2: code_to
    3: date
    4: train
    5: type
    6: car
    7: seat
    2000000 2004510 05.05.2017 663 Плац 3 16
    2004510 2000000 08.05.2017 664 Плац 3 16
    """
    code_from = int(sys.argv[1])
    code_to = int(sys.argv[2])
    date = sys.argv[3]
    needed_train = int(sys.argv[4])
    needed_type = sys.argv[5]
    needed_car = int(sys.argv[6])
    needed_seat = int(sys.argv[7])

    print(datetime.datetime.now())

    trains = check_trains(code_from, code_to, date, needed_train, needed_type)

    if not trains:
        print('Места нужного типа {} в запрошенном поезде '
              'не найдены'.format(needed_type))
        exit()

    if not needed_car:
        exit()

    print('Места нужного типа {} в запрошенном поезде найдены. '
          'Проверяем вагон и место'.format(needed_type))
    bot.sendMessage(
        chat_id=MY_TELEGRAM_ID,
        text='Места нужного типа {} в запрошенном поезде '
             'найдены.'.format(needed_type))
    for train in trains:
        assert train['number'] == train['number2']
        check_car_and_seat(code_from, code_to, date, train['number'],
                           needed_car, needed_seat)

main()
