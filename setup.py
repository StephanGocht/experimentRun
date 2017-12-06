import setuptools

setuptools.setup(
    name='experimentrun',
    license='MIT',
    version="0.0.1",
    author="Stephan Gocht",
    author_email="steohan@gobro.de",
    description=("A benchmarking framework."),
    packages=['experimentrun'],
    classifiers=[
        'Development Status :: 1 - Planning',
        'License :: OSI Approved :: MIT License'
    ],
    entry_points={
        'console_scripts': [
            'exrun=experimentrun.__main__:main',
        ]
    },
    install_requires=[
        "jsonpointer",
        "Pyro4"
    ]
)
