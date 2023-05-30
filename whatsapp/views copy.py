import json
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from heyoo import WhatsApp
from os import environ
from .models import AdminUser, Game, Player

messenger = WhatsApp(token=environ.get("TOKEN"), phone_number_id=environ.get("PHONE"))
VERIFY_TOKEN = environ.get("APP_SECRET")

CREATE_TEMPLATE_MESSAGE = """Please send me the information about the game in the following format.
Location:
Start Date:
Start Time:
Minimum Players:
Maximum Players:"""


# global is_game_info_message
# is_game_info_message = False

def index(request):
    return render(request, 'index.html')

@csrf_exempt
def whatsapi(request):
    if request.method == "GET":
        if request.GET["hub.verify_token"] == VERIFY_TOKEN:
            return HttpResponse(request.GET["hub.challenge"])

    data = json.loads(request.body.decode('utf-8'))
    try:
        value = data['entry'][0]['changes'][0]['value']
        # check if this hook is about message arriving . it might be status, delivered and so on.
        if 'messages' in value:
            messages = value['messages'][0]
            message = messages['text']['body']
            wa_id = messages['from']
            username = "Tom"
            # check if the number is the admin
            if is_admin(wa_id):
                # if the message is about creating a game
                # if not is_game_info_message and message == '/create':
                if message == '/create':
                    messenger.send_message(CREATE_TEMPLATE_MESSAGE, wa_id)
                    # is_game_info_message = True
                # if the message is the response for creating a game
                # elif is_game_info_message and message.startswith('Location'):
                elif message.startswith('Location'):
                    # parse the game info
                    message_list = message.split('\n')
                    location = message_list[0].split(':')[1]
                    start_date = message_list[1].split(':')[1]
                    start_time = message_list[2].split(':')[1]
                    min_players = message_list[3].split(':')[1]
                    max_players = message_list[4].split(':')[1]
                    
                    id = insert_game(location, start_date, start_time, min_players, max_players)
                    
                    GAME_MESSAGE = "Game ID: " + id + "\n" + message + f"""To Join the Waitlist, reply "in {id}" privately to this message.
                    To Leave the Waitlist, reply "out {id}" privately to this message.
                    """
                    # this should be sent to the group
                    messenger.send_message(GAME_MESSAGE, wa_id)
                    # is_game_info_message = False
                # if the message is invalid
                else:
                    messenger.send_message("Please send message /create to create a game.", wa_id)
            else:
                message = message.split(' ')
                # check if the message has the valid type such as "in 7235"
                if len(message) == 2:
                    action = message[0]
                    id = message[1]
                    location, start_date, start_time, min_players, max_players, playerlist = get_game_info(id)
                    # if the player is going to join the waitlist
                    if action == 'in':
                        # join the game
                        if len(playerlist) < max_players:
                            ADD_PLAYERLIST_MESSAGE = f"""Game ID: {id}
                            Location: {location}
                            Start Date: {start_date}
                            Start Time: {start_time}
                            Minimum Players: {min_players}
                            Maximum Players: {max_players}
                            
                            You have been added to the Player List!
                            
                            To Leave the Player List, reply "out {id}" to this message.
                            """
                            add_playerlist(id, username, wa_id)
                            messenger.send_message(ADD_PLAYERLIST_MESSAGE, wa_id)
                        # join the waitlist
                        else:
                            # overflow the maximum limit
                            if len(playerlist) > max_players:
                                WAITLIST_MESSAGE = f"""Game ID: {id}
                                Location: {location}
                                Start Date: {start_date}
                                Start Time: {start_time}
                                Minimum Players: {min_players}
                                Maximum Players: {max_players}
                                
                                Maximum Player Limit Reached! You have been successfully added to the Waitlist
                                
                                To Leave the Waitlist, reply "out {id}" privately to this message.
                                """
                                add_waitlist(id, username, wa_id)
                                messenger.send_message(WAITLIST_MESSAGE, wa_id)
                            
                            # reached to maximum limit
                            else:
                                MAXIMUM_MESSAGE = f"""Game ID: {id}
                                Location: {location}
                                Start Date: {start_date}
                                Start Time: {start_time}
                                Minimum Players: {min_players}
                                Maximum Players: {max_players}
                                
                                To Join the Waitlist, reply "in {id}" privately to this message.
                                To Leave the Waitlist, reply "out {id}" privately to this message.
                                
                                Maximum Player Limit Reached! Players may still join the Waitlist.
                                
                                Player List ({max_players})
                                """
                                
                                count = 1
                                for number, name in playerlist.items():
                                    MAXIMUM_MESSAGE += "\t\n" + str(count) + ".  " + name + ": " + number
                                    count += 1
                                    
                                MAXIMUM_MESSAGE += '\nWaitlist(0)'
                                
                                # send messag to the group
                                messenger.send_message(MAXIMUM_MESSAGE, wa_id)

                    # if the player is going to leave the waitlist
                    else:
                        REMOVE_MESSAGE = f"""Game ID: {id}
                        Location: {location}
                        Start Date: {start_date}
                        Start Time: {start_time}
                        Minimum Players: {min_players}
                        Maximum Players: {max_players}
                        
                        You have been successfully removed from the game!
                        """
                        remove_playerlist(id, wa_id)
                        messenger.send_message(REMOVE_MESSAGE, wa_id)
                        
                        # Send message to the first user in the waitlist
                        waitlist_number = check_waitlist(id)
                        # if there is a play in the waitlist
                        if len(waitlist_number) > 0:
                            ADD_PLAYERLIST_FROM_WAITLIST_MESSAGE = f"""Game ID: {id}
                            Location: {location}
                            Start Date: {start_date}
                            Start Time: {start_time}
                            Minimum Players: {min_players}
                            Maximum Players: {max_players}
                            
                            A player has dropped out! You have been added to the Player List!
                            
                            To Leave the Player List, reply "out {id}" to this message.
                            """
                            messenger.send_message(ADD_PLAYERLIST_FROM_WAITLIST_MESSAGE, waitlist_number)
                        # if waitlist is 0
                        else:
                            pass
                                                
                else:
                    messenger.send_message("Please reply in this format.\nin 7235 \nor\nout 7235", wa_id)
                pass

    except Exception as e:
        print("Error occurred=======================", e)

    return HttpResponse("ok")

def is_admin(wa_id):
    admin = AdminUser.objects.filter(phone_number=wa_id)
    if len(admin) > 0:
        return True
    else:
        return False

def insert_game(location, start_date, start_time, min_players, max_players):
    newGame = Game()
    newGame.location = location
    newGame.start_date = start_date
    newGame.start_time = start_time
    newGame.min_players = min_players
    newGame.max_players = max_players
    newGame.save()
    
    return newGame.id

def get_game_info(id):
    # get game info with id from games table
    game = Game.objects.get(id=id)
    location = game.location
    start_date = game.start_date
    start_time = game.start_time
    min_players = game.min_players
    max_players = game.max_players
    players = Player.objects.filter(game=id, is_playerlist=True)
    
    playerlist = {}
    for player in players:
        playerlist[player.phone_number] = player.username
        
    return location, start_date, start_time, min_players, max_players, playerlist


# add number to the playerlist
def add_playerlist(id, username, wa_id):
    newPlayer = Player()
    newPlayer.game = Game.objects.get(id=id)
    newPlayer.username = username
    newPlayer.phone_number = wa_id
    newPlayer.is_playerlist = True
    newPlayer.is_waitlist = False
    newPlayer.save()


# return playerlist
def get_playerlist(id):
    return {'Tom Sandoval':'132456', 'Jack Mason': '4567891', 'Tony':'789465'}


# add number to the waitlist
def add_waitlist(id, username, wa_id):
    newPlayer = Player()
    newPlayer.game = Game.objects.get(id=id)
    newPlayer.username = username
    newPlayer.phone_number = wa_id
    newPlayer.is_playerlist = False
    newPlayer.is_waitlist = True
    newPlayer.save()


def get_waitlist(id):
    return {'Tom Sandoval':'132456', 'Jack Mason': '4567891', 'Tony':'789465'}

# remove number from the waitlist
def remove_playerlist(id, wa_id):
    player = Player.objects.get(game=id, phone_number=wa_id)
    player.delete()


def check_waitlist(id):
    # find waitlist from the players table with id and sort them
    waitlist = Player.objects.filter(game=id, is_waitlist=True).order_by('-joined_at')
    if len(waitlist) > 0:
        waitlist[0].is_playerlist = True
        waitlist[0].is_waitlist = False
        return waitlist[0].phone_number
    else:
        return []

