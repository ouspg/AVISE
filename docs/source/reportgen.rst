Report Generation
=================================

After running SETs, a final report is generated of the instance. Reporters generate a JSON file that contains 
logs of the executed SET(s). From the JSON file, a human-readable HTML file is further generated, that includes
a summary of the executed SET(s), as well as suggestions for possible actions to take if vulnerabilities were found
in the evaluated target. 

.. toctree::
   :maxdepth: 3
   
   avise.reportgen.reporters