compbench
====

compbench is a python framework to make benchmarking and evaluation of
different tools or configurations of a tool simple. It is designed to analyse
the collected data with standart python data analysis techniques / anaconda.

Concept
----

You need:

* the tool(s) to benchmark
* a benchmark configuration
* benchmark workers, p.a.:
	* setup
	* run
	* finalize

Installation
----

Download the repository and change to the project root directory (You should
see a setup.py). Run
```pip install ./```

For instalation during development
```pip install -e ./```

Run the tool
----
```python -m experimentrun```


Misc
----

In case you want to retrive data as json and store it to mongoDB and then
pick it up with pandas:
https://medium.com/towards-data-science/mongodb-vs-pandas-5abe2c5ff6f3
