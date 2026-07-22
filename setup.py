import setuptools
from pathlib import Path

HERE = Path(__file__).parent

with open(HERE / 'README.md') as f:
    README = f.read()

CORE_REQUIRES = [
    'cooptools>=1.57',
    'PyPubSub',
    'requests',
]

EXTRAS_REQUIRE = {
    'api': ['fastapi', 'uvicorn', 'httpx', 'pydantic'],
    'persistence': ['sqlalchemy>=2.0', 'psycopg2-binary', 'coopmongo', 'pydantic'],
}
EXTRAS_REQUIRE['all'] = sorted({dep for group in EXTRAS_REQUIRE.values() for dep in group})

setuptools.setup(name='coopstorage',
      version='2.1',
      description='Package for embedded storage systems',
      url='https://github.com/tylertjburns/coopstorage',
      author='tburns',
      author_email='tyler.tj.burns@gmail.com',
      license='MIT',
      packages=setuptools.find_packages(),
      python_requires=">3.5",
      install_requires=CORE_REQUIRES,
      extras_require=EXTRAS_REQUIRE,
      long_description_content_type="text/markdown",
      long_description=README,
      zip_safe=False,
      package_data={
        "assets": ['*.css']
      },
      classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',

      ])

if __name__ == "__main__":
    print(setuptools.find_packages())