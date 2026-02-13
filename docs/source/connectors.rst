Connectors
=================================

Connectors include the logic of making requests to, and receiving responses from, AI models. Before executing any SETs on your 
target model, a connector must be configured appropriately. ``avise/configs/connector/`` directory includes template configuration 
JSON files for different types of AI model hosts. Additionally, ``avise/configs/connector/genericrest.json`` configuration file can be 
adjusted to connect to models accessible via any REST API endpoint. 

.. toctree::
   :maxdepth: 1

   avise.connectors.languagemodel
