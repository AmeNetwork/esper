from openai import OpenAI
import os
import json

class Agent:
    def __init__(self, **properties):

        self.name = properties["name"]
        self.model = properties["model"]
        self.description = properties["description"]
        self.memory = properties.get("memory", None)
        self.knowledge = properties.get("knowledge", None)

        self.tools = properties.get("tools", None)
        self.chat2web3 = properties.get("chat2web3", None)

        self.max_completion_tokens = properties.get("max_completion_tokens", None)
        self.max_token = properties.get("max_token", None)

        self.tools_functions=[]
        self.__setup()

    def get_info(self):
        return {
            "name": self.name,
            "model": self.model,
            "description": self.description,
            "memory": self.memory,
            "knowledge": self.knowledge,
            "tools": self.tools,
            "chat2web3": self.chat2web3,
            "max_completion_tokens": self.max_completion_tokens,
            "max_token": self.max_token
        }

    def __setup(self):
     
        self.agent = OpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPEN_AI_KEY"),
        )

        # set tools
        if self.tools:
            self.tools_functions=self.tools.get_tools()
           
        # set chat2web3
        if self.chat2web3:
            self.tools_functions.extend(self.chat2web3.get_onchain().functions)

    def chat(self, text, uid=None):

        if uid is None:
            uid = self.name

        system_message = {"role": "system", "content": self.description}
        messages = [system_message]

        # set knowledge
        if self.knowledge:
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            knowledge_result = self.knowledge.query(text)
            if len(knowledge_result["documents"][0]) > 0:
                knowledge_content = "\n".join(
                    f"{i+1}. {item}"
                    for i, item in enumerate(knowledge_result["documents"][0])
                )
                knowledge_message = {
                    "role": "assistant",
                    "content": knowledge_content,
                }
                messages.append(knowledge_message)

        user_message = {"role": "user", "content": text}

        # set memory
        if self.memory:
            history = self.memory.query(key=uid)
            if history:
                for item in history:
                    messages.append({"role": item["role"], "content": item["content"]})
            self.memory.insert(
                key=uid,
                role=user_message["role"],
                content=user_message["content"],
            )

        messages.append(user_message)

        response = self.agent.chat.completions.create(
            model=self.model,
            tools=self.tools_functions,
            messages=messages,
            max_completion_tokens=self.max_completion_tokens,
            max_tokens=self.max_token,
        )

        function_message = response.choices[0].message

        if function_message.tool_calls:

            function = function_message.tool_calls[0].function

            function_rsult=None

            if self.chat2web3.is_onchain_tool_function(function.name):

                function_rsult = self.chat2web3.call(function)

        
            else:

                function_rsult=self.tools.get_function(function.name)["function"](**json.loads(function.arguments))



            tool_message = {
                "role": "tool",
                "tool_call_id": function_message.tool_calls[0].id,
                "content": function_rsult,
            }
            messages.append(function_message)
            messages.append(tool_message)

            tool_response = self.agent.chat.completions.create(
                model=self.model,
                tools=self.tools_functions,
                messages=messages,
                max_completion_tokens=self.max_completion_tokens,
                max_tokens=self.max_token,
            )

            return_message = {
                "role": "assistant",
                "content": tool_response.choices[0].message.content,
            }

            if self.memory:
                self.memory.insert(
                    key=uid,
                    role=return_message["role"],
                    content=return_message["content"],
                )

            return return_message["content"]

        else:

            return_message = {"role": "assistant", "content": function_message.content}
            if self.memory:
                self.memory.insert(
                    key=uid,
                    role=return_message["role"],
                    content=return_message["content"],
                )
            return return_message["content"]
