class InvalidIP(Exception):
    def __init__(self, ip):
        super().__init__(f"The IP address {ip} is not valid.")
