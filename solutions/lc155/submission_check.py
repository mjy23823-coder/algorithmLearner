class MinStack:

    def __init__(self):
        stack = []
        min_stack = []

    def push(self, value: int) -> None:
        if not min_stack:
            min_stack.push(value)
        else:
            if value<stack[-1]:
                min_stack.push(value)

    def pop(self) -> None:
        stack.pop()
        min_stack.pop()

    def top(self) -> int:
        return stack[-1]

    def getMin(self) -> int:
        return min_stack[-1]
