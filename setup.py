from setuptools import setup, find_packages

setup(
    name='my_package',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'pandas',
        'openai',
    ],
    entry_points={
        'console_scripts': [
            'my_package = my_package.main:main',
        ],
    },
    package_data={
        'my_package': ['prompts/*.txt', 'prompt_config.json'],
    },
    author='Your Name',
    author_email='your.email@example.com',
    description='A package for processing and analyzing chat data.',
    url='https://github.com/yourusername/my_package',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
) 