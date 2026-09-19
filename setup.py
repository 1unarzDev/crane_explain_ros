from setuptools import find_packages, setup

package_name = "crane_explain_ros"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Anonymous Researcher",
    maintainer_email="research@example.invalid",
    description="Passive Nav2 evidence capture for explanation research",
    license="Apache-2.0",
    entry_points={"console_scripts": ["capture = crane_explain_ros.capture:main"]},
)

