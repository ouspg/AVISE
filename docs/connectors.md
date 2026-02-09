# TODO: Write documentation on what connectors are and how they work

Connectors handle the communication between AVISE and target system APIs. 

Connectors communicate with different backends by sending test prompts to them in a desired format, retrieving the outputs from the LLMs / AI models, and
sending original test prompts along with the output to an evaluative language model (ELM) for further vulnerability analysis.  

By abstracting the communication with different APIs to different connectors users can focus more on developing test cases and just pick a suitable API client
for their use case.