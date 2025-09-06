from pydantic.type_adapter import P


class Test():
    def __init__(self, nums:int = 0):
        self.nums: int = nums
    
    @property 
    def available(self) -> bool:
        return self.nums !=0

t = Test(10)
print(t.available)

print("---更新---")

print(t.available)

t.nums = 0 
if t.available:
    print("错误更新")
else:
    print("正确：nums为0，不可用") 