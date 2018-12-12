# brilleaux

## Introduction

Brilleaux is a DLCS services which queries an Elucidate annotation server
and returns Open Annotation annotations from W3C Web Annotations.

The purpose is, for example, to provide annotation lists to applications such as Mirador
from W3C Web Annotation sources.

Brilleaux uses:

[https://pyelucidate.readthedocs.io/en/latest/pyelucidate.html#pyelucidate.pyelucidate.async_items_by_container](https://pyelucidate.readthedocs.io/en/latest/pyelucidate.html#pyelucidate.pyelucidate.async_items_by_container)
[https://pyelucidate.readthedocs.io/en/latest/pyelucidate.html#pyelucidate.pyelucidate.format_results](https://pyelucidate.readthedocs.io/en/latest/pyelucidate.html#pyelucidate.pyelucidate.format_results)
[https://pyelucidate.readthedocs.io/en/latest/pyelucidate.html#pyelucidate.pyelucidate.mirador_oa](https://pyelucidate.readthedocs.io/en/latest/pyelucidate.html#pyelucidate.pyelucidate.mirador_oa)

functions from the [PyElucidate](https://pyelucidate.readthedocs.io/en/latest/index.html) library.

## Installation

Brilleaux provides a `Dockerfile` to run a containerised version of the service.


```bash
docker build -t brilleaux/local .
docker run -p-e BRILLEAUX_ELUCIDATE_URI="https://elucidate.example.org"  5000:5000  brilleaux/local:latest
```

the above shell commands will run a local version of Brilleaux on port 5000, with
`https://elucidate.example.org` as the source annotation server.

# Contribution Guidelines

Brilleaux has been tested using Python 3.5+. 

Feel free to raise Github issues. 

If you find an issue you are interested in fixing you can:


* Fork the repository
* Clone the repository to your local machine
* Create a new branch for your fix using `git checkout -b branch-name-here`.
* Fix the issue.
* Commit and push the code to your remote repository.
* Submit a pull request to the `brilleaux` repository, with a description of your fix and the issue number.
* The PR will be reviewed by the maintainer [https://github.com/mattmcgrattan](https://github.com/mattmcgrattan) and either merge the PR or response with comments.

Thanks!
# License

MIT License

Copyright (c) Digirati 2018

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.