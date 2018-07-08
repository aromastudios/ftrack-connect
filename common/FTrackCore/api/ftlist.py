class FTList(list):
    """
    Extended list
    """
    
    def __init__(self,objectType=None,objects=None):
        super(FTList,self).__init__()
        
        #handle multiple types
        if type(objectType).__name__ == 'list' and objects:
            for obj in objects:
                
                for t in objectType:
                    
                    if t._type == obj.get('entityType'):
                        self.append(t(dict=obj))
                        break
                
                       
                
                 
        elif objectType and objects:
            for obj in objects:
                self.append(objectType(dict=obj))
                

        
    
    def sort(self, how='asc', onWhat='name'):
        """
        Sort
        @param  how  asc or desc
        @param  onWhat  Sorting parameter
        """

        def mySort(val1, val2):
            value1 = val1.get(onWhat)
            value2 = val2.get(onWhat)
            if (type(value1) != type("str")  and type(value2) != type("str")):
                value1 = float(value1)
                value2 = float(value2)
            if (how == "asc"):
                if value1 < value2:
                    return - 1
                else:
                    return 1
            elif (how == "desc"):
                if value1 > value2:
                    return - 1
                else:
                    return 1

        super(FTList, self).sort(mySort)
    
    
    def find(self,key,value):
        """
        Find 
        @param  key  used to fetch a value from objects in list
        @param  value  the value we are looking for
        """
        for item in self:
            if item.get(key) == value:
                return item
            
        return None