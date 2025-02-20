from setuptools import setup, find_packages

setup(
    name='analyzer_agent',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pandas',
        'openai',
    ],
    entry_points={
        'console_scripts': [
            'analyzer_agent = analyzer_agent.main:main',
        ],
    },
    package_data={
        'analyzer_agent': ['prompts/*.txt', 'prompt_config.json'],
    },
    author='Your Name',
    author_email='your.email@example.com',
    description='A package for processing and analyzing chat data.',
    url='https://github.com/yourusername/analyzer_agent',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
) 