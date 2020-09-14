import traceback


def boundary(name):
    def _withName(func):
        def _withTryExcept(*args):
            try:
                return func(*args)
            except:
                print("error in {}:\n{}".format(name, traceback.format_exc()))
                return None

        return _withTryExcept

    return _withName
