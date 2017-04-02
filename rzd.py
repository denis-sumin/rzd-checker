# coding=utf-8
import datetime
import logging
import sys
import time
import traceback

import requests
import telegram

from settings import BOT_TOKEN, CHECK_EVERY, MY_TELEGRAM_ID

REQUEST_TIMEOUT = 10.

bot = telegram.Bot(token=BOT_TOKEN)
logger = logging.getLogger(__name__)
request_data = {
    'cookies': None,
}


class TrainInfo:
    from_ = None
    to = None
    train_number = None
    date = None
    requested_car_type = None
    requested_car_number = None
    requested_seat_number = None


class CheckResult:
    train_found = None
    car_type_found = None
    car_number_found = None
    seat_number_found = None
    available_seats = None


def join_seat_numbers(seat_numbers):
    if seat_numbers:
        return ', '.join((str(s) for s in sorted(list(seat_numbers))))
    else:
        return 'нет'


def get_data(url, data, cookies):
    r_rid = requests.post(url, data=data, cookies=cookies,
                          timeout=REQUEST_TIMEOUT)
    try:
        if r_rid.json()['result'] == 'RID':
            data['rid'] = r_rid.json()['RID']
        else:
            raise RuntimeError('No RID')
    except Exception as e:
        print(e)
        raise

    while True:
        r_data = requests.post(url, data=data, cookies=cookies,
                               timeout=REQUEST_TIMEOUT)
        try:
            if r_data.json()['result'] == 'OK':
                break
            elif r_data.json()['result'] == 'RID':
                data['rid'] = r_rid.json()['RID']
                continue
            else:
                raise RuntimeError('Unexpecred result', r_data.json())
        except Exception as e:
            print(e)
            continue

    return r_data.json()


def check_trains(code_from, code_to, date, train_number, car_type):

    url = 'https://pass.rzd.ru/timetable/public/ru?layer_id=5827'
    data = {
        'checkSeats': 1,
        'code0': code_from,
        'code1': code_to,
        'dir': 0,
        'dt0': date,
        'tfl': 3,
    }

    data = get_data(url, data, request_data['cookies'])
    assert len(data['tp']) == 1

    train_info = TrainInfo()
    train_info.from_ = data['tp'][0]['from']
    train_info.to = data['tp'][0]['where']
    train_info.date = data['tp'][0]['date']

    trains = data['tp'][0]['list']

    train_found = False
    trains_with_requested_car_type = list()

    for train in trains:
        if (
                str(train_number) in train['number'] or
                str(train_number) in train['number2']
        ):
            train_found = True
            logging.info('Запрошенный поезд {} найден'.format(train_number))
            for t in train['cars']:
                if t['type'] == car_type:
                    trains_with_requested_car_type.append(train)
    return train_found, trains_with_requested_car_type, train_info


def check_car_and_seat(code_from, code_to, date, train_number,
                       car_number, seat_number=None):
    data = {
        'dir': 0,
        'seatDetails': 1,
        'code0': code_from,
        'code1': code_to,
        'tnum0': train_number,
        'dt0': date,
        'bEntire': 'false',
    }
    url = 'https://pass.rzd.ru/timetable/public/ru?layer_id=5764'
    data = get_data(url, data, request_data['cookies'])
    assert len(data['lst']) == 1
    cars = data['lst'][0]['cars']

    found_car = False
    found_seat = False
    available_seats = None

    for car in cars:
        if int(car['cnumber']) == car_number:
            found_car = True
            logger.info('Найден нужный вагон: {}'.format(car_number))
            if not seat_number:
                break
            available_seats = sorted([
                int(s2) for s1 in car['seats']
                for s2 in s1['places'].split(',')])
            if seat_number in available_seats:
                found_seat = True
                logger.info('Запрошенное место {} найдено!'
                            .format(seat_number))
            else:
                logger.info(
                    'Запрошенное место {} не найдено. Доступны места: {}'
                    .format(seat_number, join_seat_numbers(available_seats)))
    if not found_car:
        logger.info('Нужный вагон {} не найден'.format(car_number))

    return found_car, found_seat, available_seats


def perform_check(code_from, code_to, date, train_number,
                  car_type, car_number, seat_number):
    r = requests.get('https://pass.rzd.ru', timeout=REQUEST_TIMEOUT)
    request_data['cookies'] = r.cookies

    result = CheckResult()

    train_found, trains_with_requested_car_type, train_info = check_trains(
        code_from, code_to, date, train_number, car_type)

    train_info.train_number = train_number
    train_info.requested_car_type = car_type
    train_info.requested_car_number = car_number
    train_info.requested_seat_number = seat_number

    result.train_found = train_found
    result.car_type_found = bool(trains_with_requested_car_type)
    if trains_with_requested_car_type:
        logger.info('Места нужного типа {} в запрошенном поезде найдены. '
                    'Проверяем вагон и место'.format(car_type))
        result.car_type_found = True
    else:
        logger.info('Места нужного типа {} в запрошенном поезде '
                    'не найдены'.format(car_type))
        result.car_type_found = False

    assert len(trains_with_requested_car_type) <= 1, \
        'Найдено больше одного поезда с запрошенным номером'

    if trains_with_requested_car_type:
        train = trains_with_requested_car_type[0]
        assert train['number'] == train['number2']
        train_info.train_number = train['number']

        if car_number:
            found_car, found_seat, available_seats = check_car_and_seat(
                code_from, code_to, date, train['number'],
                car_number, seat_number)
            result.car_number_found = found_car
            result.seat_number_found = found_seat
            result.available_seats = set(available_seats)

    return result, train_info


def process_check_result_human(check_result, last_check_result, train_info):
    call_needed = False

    if last_check_result.train_found == check_result.train_found:
        if last_check_result.car_type_found == check_result.car_type_found:
            #
            pass
        else:
            if check_result.car_type_found:
                pass
            else:
                pass
    else:
        if check_result.train_found:
            if check_result.car_type_found:
                train_message = \
                    'Появились билет на поезд {train_number} ' \
                    '({from_} {to} {date})'.format(
                        train_number=train_info.train_number,
                        from_=train_info.from_,
                        to=train_info.to,
                        date=train_info.date,
                    )
                if check_result.car_type_found:
                    if check_result.car_number_found:
                        if check_result.seat_number_found:
                            call_needed = True
                            message = \
                                '{}. Необходимое место {} в вагоне {} типа {} ' \
                                'доступно для покупки'.format(
                                    train_message,
                                    train_info.requested_seat_number,
                                    train_info.requested_car_number,
                                    train_info.requested_car_type
                                )
                        else:
                            message = \
                                '{}. В вагоне {} ({}) доступны следующие ' \
                                'места: {}.'.format(
                                    train_message,
                                    train_info.requested_car_number,
                                    train_info.requested_car_type,
                                    join_seat_numbers(check_result.available_seats),  # noqa
                                )
                    else:
                        message = \
                            '{}. В поезде есть места нужного типа {}, ' \
                            'но нет мест в нужном вагоне {}.'.format(
                                train_message,
                                train_info.requested_car_type,
                                train_info.requested_car_number,
                            )
                else:
                    message = '{}. В поезде нет мест нужного типа {}.'.format(
                        train_message, train_info.requested_car_type)
        else:
            message = \
                'В продаже больше нет билетов на поезд {train_number} ' \
                '({from_} {to} {date}).'.format(
                    train_number=train_info.train_number,
                    from_=train_info.from_,
                    to=train_info.to,
                    date=train_info.date,
                )
    return message, call_needed


def bool_to_russian(v):
    return 'да' if bool(v) else 'нет'


def process_check_result(check_result, last_check_result, train_info):
    call_needed = False
    message = None

    order = (
        'train_found',
        'car_type_found',
        'car_number_found',
        'seat_number_found',
        'available_seats',
    )

    for attr in order:
        if getattr(last_check_result, attr) != getattr(check_result, attr):
            message = (
                'Новая информация по запросу: поезд {train_number}, '
                '{from_} → {to}, {date}.\n'
                'Поезд найден: {train_found}.\n'
                'Места типа {car_type}: {car_type_found}.\n'
                'Вагон {car_number}: {car_number_found}.\n'
                'Место {seat_number}: {seat_number_found}.\n'
                'Доступные места: {available_seats}.'.format(
                    train_number=train_info.train_number,
                    from_=train_info.from_,
                    to=train_info.to,
                    date=train_info.date,
                    train_found=bool_to_russian(check_result.train_found),
                    car_type=train_info.requested_car_type,
                    car_type_found=bool_to_russian(check_result.car_type_found),
                    car_number=train_info.requested_car_number,
                    car_number_found=bool_to_russian(check_result.car_number_found),
                    seat_number=train_info.requested_seat_number,
                    seat_number_found=bool_to_russian(check_result.seat_number_found),
                    available_seats=join_seat_numbers(check_result.available_seats),
                )
            )
            if attr == 'seat_number_found' and check_result.seat_number_found:
                call_needed = True

    return message, call_needed


def run_checker(code_from, code_to, date, train_number,
                car_type, car_number, seat):
    last_check_result = CheckResult()
    last_result_timestamp = 0
    last_tb = None
    while True:
        try:
            check_result, train_info = perform_check(
                code_from, code_to, date, train_number, car_type, car_number, seat)
        except requests.exceptions.Timeout:
            if time.time() - last_result_timestamp > 60:
                last_result_timestamp = time.time()
                bot.sendMessage(
                    chat_id=MY_TELEGRAM_ID,
                    text='Не удалось получить данные с сайта РЖД')
            else:
                continue
        except Exception:
            tb = traceback.format_exc()
            if tb != last_tb:
                bot.sendMessage(
                    chat_id=MY_TELEGRAM_ID,
                    text='Unhandled exception. Traceback: {}'.format(tb))
            last_tb = tb
        else:
            message, call_needed = process_check_result(
                check_result, last_check_result, train_info)

            if message:
                bot.sendMessage(
                    chat_id=MY_TELEGRAM_ID,
                    text='{}\nЗвоним: {}'.format(
                        message, bool_to_russian(call_needed)))

            last_check_result = check_result
            last_result_timestamp = time.time()
            last_tb = None
        time.sleep(CHECK_EVERY)


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
    train_number = int(sys.argv[4])
    car_type = sys.argv[5]
    car_number = int(sys.argv[6])
    seat_number = int(sys.argv[7])

    run_checker(code_from, code_to, date, train_number, car_type,
                car_number, seat_number)


main()
