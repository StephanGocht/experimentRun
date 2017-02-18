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
