class ResultParser :
     
    def __init__(self, lang_chain_result):
        self.lang_chain_result = lang_chain_result

    def serialize(self) :
        context_list = []

        for item in self.lang_chain_result['context']:
            context_dict = {}
            context_dict['metadata'] = item.metadata 
            context_dict['page_content'] = item.page_content
            context_list.append(context_dict)

        
        return {"input": self.lang_chain_result['input'],
                "answer": self.lang_chain_result['answer'],
                "context": context_list}
        