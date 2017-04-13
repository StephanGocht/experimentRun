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
```pip install experimentrun```

For instalation during development
```pip install -e experimentrun```

Run the tool
----
```python -m experimentrun```

