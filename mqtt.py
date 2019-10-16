import paho.mqtt.client as mqtt
from DQNAgent import DQNAgent


class Server:
    def __init__(self, host, game, player):
        self._client = mqtt.Client()
        self._game = game
        self._player = player
        self._agent = DQNAgent(game, True)
        self._observation = self._game.reset()
        self._done = False
        self._repeated_actions = 0
        self._history = []

        self._client.connect(host)
        self._client.subscribe('Zumo/#', 0)
        self._client.on_message = self.on_message

    def play(self, model_games):
        self._agent.load_model(model_games, True)

        print('Sending ready status')
        self._client.publish('Net/Status', 'Ready')
        self._client.loop_forever()

    def on_message(self, client, obj, msg):
        if 'Start' in msg.topic:
            print('\nReceived robot start confirmation')
            self._client.publish('Net/Ack', 'Start')
            self._game.reset()
            self._history = []
            self._observation = self._game.observe()
            action = self._agent.predict(self._observation)
            self._client.publish('Net/Action', int(action))
            print('Sending next action order')

        elif 'Coords' in msg.topic:
            print('Received request of current coordinates')
            self._client.publish('Net/Ack', 'Coords')
            coords = self._player.get_coords()
            self._client.publish('Net/Coords', f'{coords}')
            print('Sending coordinates')

        elif 'Move' in msg.topic:
            print('Received move confirmation')
            self._client.publish('Net/Ack', 'Move')
            if not self._done:
                self._observation = self._game.observe()
                action = self._agent.predict(self._observation)
                _, _, self._done, _ = self._game.step(action)

                if self._player.get_coords() in self._history:
                    self._repeated_actions += 1
                    if self._repeated_actions > 5:
                        self._client.publish('Net/Status', 'Stuck')
                        print('Agent stuck. Sending stuck signal')
                        self._client.disconnect()

                if not self._done:
                    self._history.append(self._player.get_coords())
                    self._client.publish('Net/Action', int(action))
                    print('Sending next action order')

            if self._done:
                print('Game complete. Sending finish status')
                self._client.publish('Net/Status', 'Finish')
                self._client.disconnect()

        elif 'Obst' in msg.topic:
            print('Received obstacle info')
            string = msg.payload.decode('utf-8')
            obstacle = tuple(map(int, string[1:-1].split(", ", 1)))
            self._game.add_obstacle(obstacle)
            self._client.publish('Net/Ack', f'Obst {obstacle}')
            print(f'Sending obstacle {obstacle} acknowledgement')
