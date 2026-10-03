from setuptools import find_packages, setup

package_name = 'sysml2owl'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(),
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name],
        ),
        (
            'share/' + package_name,
            ['package.xml'],
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='esther',
    maintainer_email='',
    description='SysML v2 to OWL converter',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'sysml2owl = sysml2owl.cli:main',
        ],
    },
)