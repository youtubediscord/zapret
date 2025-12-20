class Printer:
    def put(self, msg):
        print(msg)

from build_zapret.github_release import test_github_connection
test_github_connection(Printer())
