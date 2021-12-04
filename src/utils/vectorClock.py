from collections import defaultdict
from functools import wraps
from threading import Lock
from copy import deepcopy
from typing import Callable, List

MESSAGE = "message"
MESSAGE_COUNT = "message_count"
SENDER_ID = "sender_id"


def create_with_vector_locks(lock_names: List[str]):
    """
    Decorator that acquires locks with the specified names.
    Used in VectorClock class.
    """
    lock_names.sort()

    def with_vector_locks(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for lock_name in lock_names:
                self.locks[lock_name].acquire()
                result = func(self, *args, **kwargs)
                self.locks[lock_name].release()
                return result

        return wrapper

    return with_vector_locks


class VectorClock:
    """
    Mantains logic clocks for all other processes. Executes logic for
    message synchronization on a process independent basis. This means
    that messages from a specific client will have their sending
    order preserved, but there is no such guarantee for messages of
    different clients
    """

    def __init__(self, idx: str, onDeliverMessage: Callable[[dict], None]) -> None:
        self.idx = idx
        # { destination_id: message_count }
        self.sent_messages = defaultdict(lambda: 0)

        # { sender_id: message_count }
        self.received_messages = defaultdict(lambda: 0)

        # Delayed messages
        self.delayed_messages = []

        # Locks
        lock_names = ["sent_messages", "received_messages", "delayed_messages"]
        self.locks = {x: Lock() for x in lock_names}

        # Callback when message is delivered
        self.onDeliverMessage = onDeliverMessage

    @create_with_vector_locks(["sent_messages"])
    def send_message(self, message_txt: str, dest_id: str):
        """
        Public method to send a message. Will execute logic clock algorithm.
        """
        # Increase count of messages sent to the destination
        self.sent_messages[dest_id] += 1

        message = {
            MESSAGE: message_txt,
            # Include count of messages sent to the destination in message
            MESSAGE_COUNT: self.sent_messages[dest_id],
            SENDER_ID: self.idx,
        }

        return message

    def receive_message(self, message: dict):
        """
        Public method to receive a message. Will execute logic clock algorithm,
        delaying the delivery of a message if previous messages are missing.
        """
        if self.__should_delay_message(message):
            self.delayed_messages.append(message)
        else:
            self.__deliver_message(message)
            self.__check_delayed_messages()

    @create_with_vector_locks(["received_messages"])
    def __should_delay_message(self, message: dict) -> bool:
        """
        Checks if a message should be delayed. This should happen if a
        previous message hasn't been received yet.
        """
        sender_id = message[SENDER_ID]
        message_count = message[MESSAGE_COUNT]

        # If the amount of messages sent by the sender to this client
        # exceeds the messages received from him by more than 1,
        # this means that there are still undelivered messages that
        # predate this one.
        return message_count - 1 > self.received_messages[sender_id]

    @create_with_vector_locks(["received_messages"])
    def __deliver_message(self, message: dict):
        """
        Executes the delivery of a message via the onDeliverMessage callback.
        Also updates the received message count from the sender.
        """
        sender_id = message[SENDER_ID]
        self.received_messages[sender_id] = max(
            message[MESSAGE_COUNT], self.received_messages[sender_id] + 1
        )
        self.onDeliverMessage(message)

    @create_with_vector_locks(["delayed_messages"])
    def __check_delayed_messages(self):
        """
        Checks if a delayed message should now be delivered. Does this
        untill no more messages can be delivered.
        """
        message_delivered = True

        while message_delivered:
            message_delivered = False
            for i, message in enumerate(self.delayed_messages):
                if self.__should_delay_message(message):
                    continue

                self.delayed_messages.pop(i)
                self.__deliver_message(message)
                message_delivered = True
                break

    def load_from(self, sent_messages: dict, received_messages: dict):
        self.sent_messages.update(sent_messages)
        self.received_messages.update(received_messages)
        return self

    def dump(self):
        return [dict(self.sent_messages), dict(self.received_messages)]


if __name__ == "__main__":

    def deliverMessage(idx, message):
        print(f"{idx}: {message[MESSAGE]}")

    clock_a = VectorClock("a", lambda m: deliverMessage("a", m))
    clock_b = VectorClock("b", lambda m: deliverMessage("b", m))
    clock_c = VectorClock("c", lambda m: deliverMessage("c", m))

    m1 = clock_b.send_message("b1", "a")
    m2 = clock_b.send_message("b2", "a")
    m3 = clock_b.send_message("b3", "a")

    clock_a.receive_message(m3)
    clock_a.receive_message(m2)
    clock_a.receive_message(m1)

    m1 = clock_b.send_message("b4", "c")
    m2 = clock_b.send_message("b5", "c")
    m3 = clock_b.send_message("b6", "c")

    clock_c.receive_message(m3)
    clock_c.receive_message(m2)
    clock_c.receive_message(m1)

    m1 = clock_b.send_message("b7", "a")
    m2 = clock_b.send_message("b8", "c")
    m3 = clock_b.send_message("b9", "a")

    clock_a.receive_message(m3)
    clock_c.receive_message(m2)
    clock_a.receive_message(m1)
