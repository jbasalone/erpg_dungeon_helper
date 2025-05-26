
import sqlitedict

db = sqlitedict.SqliteDict('d11_solutions.sqlite', autocommit=True)


def print_d11_board(board_code):

    count = 0
    for letter in board_code:
        if letter == '0':
            print('S', end='')
        else:
            print('F', end='')

        count += 1
        if count % 3 == 0:
            count = 0
            print()

    print('FPF')


MAX_COMBINATIONS = 64


def generate_all_solutions():

    for i in range(MAX_COMBINATIONS):
        board_code = bin(i)[2:]
        if len(board_code) < 6:
            board_code = '0' * (6 - len(board_code)) + board_code

        # if board_code in db:
        #     print(db[board_code])
        #     continue

        print_d11_board(board_code)

        response = input(f"Path {i+1}/{MAX_COMBINATIONS}: ").upper()

        print(response, board_code)

        print()

        db[board_code] = response


if __name__ == '__main__':
    generate_all_solutions()






