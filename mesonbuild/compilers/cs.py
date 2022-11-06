# Copyright 2012-2017 The Meson development team

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os.path, subprocess
from subprocess import PIPE
import textwrap
import typing as T

from ..mesonlib import EnvironmentException
from ..linkers import RSPFileSyntax

from .compilers import Compiler, MachineChoice, mono_buildtype_args
from .mixins.islinker import BasicLinkerIsCompilerMixin

if T.TYPE_CHECKING:
    from ..envconfig import MachineInfo
    from ..environment import Environment

cs_optimization_args = {'0': [],
                        'g': [],
                        '1': ['-optimize+'],
                        '2': ['-optimize+'],
                        '3': ['-optimize+'],
                        's': ['-optimize+'],
                        }  # type: T.Dict[str, T.List[str]]


class CsCompiler(BasicLinkerIsCompilerMixin, Compiler):

    language = 'cs'

    def __init__(self, exelist: T.List[str], version: str, for_machine: MachineChoice,
                 info: 'MachineInfo', runner: T.Optional[str] = None):
        super().__init__(exelist, version, for_machine, info)
        self.runner = runner

    @classmethod
    def get_display_language(cls) -> str:
        return 'C sharp'

    def get_always_args(self) -> T.List[str]:
        return ['/nologo']

    def get_linker_always_args(self) -> T.List[str]:
        return ['/nologo']

    def get_output_args(self, fname: str) -> T.List[str]:
        return ['-out:' + fname]

    def get_link_args(self, fname: str) -> T.List[str]:
        return ['-r:' + fname]

    def get_werror_args(self) -> T.List[str]:
        return ['-warnaserror']

    def get_pic_args(self) -> T.List[str]:
        return []

    def compute_parameters_with_absolute_paths(self, parameter_list: T.List[str],
                                               build_dir: str) -> T.List[str]:
        for idx, i in enumerate(parameter_list):
            if i[:2] == '-L':
                parameter_list[idx] = i[:2] + os.path.normpath(os.path.join(build_dir, i[2:]))
            if i[:5] == '-lib:':
                parameter_list[idx] = i[:5] + os.path.normpath(os.path.join(build_dir, i[5:]))

        return parameter_list

    def get_pch_use_args(self, pch_dir: str, header: str) -> T.List[str]:
        return []

    def get_pch_name(self, header_name: str) -> str:
        return ''

    def sanity_check(self, work_dir: str, environment: 'Environment') -> None:
        src = 'sanity.cs'
        obj = 'sanity.exe'
        source_name = os.path.join(work_dir, src)
        with open(source_name, 'w', encoding='utf-8') as ofile:
            ofile.write(textwrap.dedent('''
                public class Sanity {
                    static public void Main () {
                    }
                }
                '''))
        pc = subprocess.Popen(self.exelist + self.get_always_args() + [src], cwd=work_dir)
        pc.wait()
        if pc.returncode != 0:
            raise EnvironmentException('C# compiler %s can not compile programs.' % self.name_string())
        if self.runner:
            cmdlist = [self.runner, obj]
        else:
            cmdlist = [os.path.join(work_dir, obj)]
        pe = subprocess.Popen(cmdlist, cwd=work_dir)
        pe.wait()
        if pe.returncode != 0:
            raise EnvironmentException('Executables created by Mono compiler %s are not runnable.' % self.name_string())

    def needs_static_linker(self) -> bool:
        return False

    def get_buildtype_args(self, buildtype: str) -> T.List[str]:
        return mono_buildtype_args[buildtype]

    def get_debug_args(self, is_debug: bool) -> T.List[str]:
        return ['-debug'] if is_debug else []

    def get_optimization_args(self, optimization_level: str) -> T.List[str]:
        return cs_optimization_args[optimization_level]


class MonoCompiler(CsCompiler):

    id = 'mono'

    def __init__(self, exelist: T.List[str], version: str, for_machine: MachineChoice,
                 info: 'MachineInfo'):
        super().__init__(exelist, version, for_machine, info, runner='mono')

    def rsp_file_syntax(self) -> 'RSPFileSyntax':
        return RSPFileSyntax.GCC


class VisualStudioCsCompiler(CsCompiler):

    id = 'csc'

    def get_buildtype_args(self, buildtype: str) -> T.List[str]:
        res = mono_buildtype_args[buildtype]
        if not self.info.is_windows():
            tmp = []
            for flag in res:
                if flag == '-debug':
                    flag = '-debug:portable'
                tmp.append(flag)
            res = tmp
        return res

    def rsp_file_syntax(self) -> 'RSPFileSyntax':
        return RSPFileSyntax.MSVC

class DotnetCompiler(CsCompiler):

    id = 'dotnet'

    def __init__(self, exelist: T.List[str], version: str, for_machine: MachineChoice,
                 info: 'MachineInfo'):
        output, _ = subprocess.Popen(exelist + ['--list-sdks'], stdout=PIPE, text=True).communicate()
        # sdk_path = [x.split(' ')[1].strip('[]') for x in output.strip().splitlines() if x.startswith(version)]
        sdk_path = ["C:/Program Files/dotnet/sdk"]
        # print(sdk_path)
        compiler_rel_path = [version, 'Roslyn', 'bincore', 'csc.dll']
        compiler_path = '/'.join(sdk_path + compiler_rel_path)

        exelist += [compiler_path]
        # Location specified here: https://github.com/dotnet/designs/blob/main/accepted/2019/targeting-packs-and-runtime-packs.md
        self.packs_path = '/'.join(sdk_path + ['..', 'packs'])
        self.runtime_version = '6.0.5' # TODO:
        self.framework_version = 'net6.0'
        super().__init__(exelist, version, for_machine, info, runner='dotnet')

    def get_always_args(self) -> T.List[str]:

        default_refs = [f"/reference:{self.packs_path}/Microsoft.NETCore.App.Ref/{self.runtime_version}/ref/{self.framework_version}/{x}" for x in [
            'Microsoft.CSharp.dll',
            'Microsoft.Win32.Primitives.dll',
            'System.dll',
            'System.Core.dll',
            'mscorlib.dll',
            'netstandard.dll',
            'System.Runtime.dll',
            'Microsoft.VisualBasic.Core.dll',
            'Microsoft.VisualBasic.dll',
            'Microsoft.Win32.Registry.dll',
            'System.AppContext.dll',
            'System.Buffers.dll',
            'System.Collections.Concurrent.dll',
            'System.Collections.dll',
            'System.Collections.Immutable.dll',
            'System.Collections.NonGeneric.dll',
            'System.Collections.Specialized.dll',
            'System.ComponentModel.Annotations.dll',
            'System.ComponentModel.DataAnnotations.dll',
            'System.ComponentModel.dll',
            'System.ComponentModel.EventBasedAsync.dll',
            'System.ComponentModel.Primitives.dll',
            'System.ComponentModel.TypeConverter.dll',
            'System.Configuration.dll',
            'System.Console.dll',
            'System.Data.Common.dll',
            'System.Data.DataSetExtensions.dll',
            'System.Data.dll',
            'System.Diagnostics.Contracts.dll',
            'System.Diagnostics.Debug.dll',
            'System.Diagnostics.DiagnosticSource.dll',
            'System.Diagnostics.FileVersionInfo.dll',
            'System.Diagnostics.Process.dll',
            'System.Diagnostics.StackTrace.dll',
            'System.Diagnostics.TextWriterTraceListener.dll',
            'System.Diagnostics.Tools.dll',
            'System.Diagnostics.TraceSource.dll',
            'System.Diagnostics.Tracing.dll',
            'System.Drawing.dll',
            'System.Drawing.Primitives.dll',
            'System.Dynamic.Runtime.dll',
            'System.Formats.Asn1.dll',
            'System.Globalization.Calendars.dll',
            'System.Globalization.dll',
            'System.Globalization.Extensions.dll',
            'System.IO.Compression.Brotli.dll',
            'System.IO.Compression.dll',
            'System.IO.Compression.FileSystem.dll',
            'System.IO.Compression.ZipFile.dll',
            'System.IO.dll',
            'System.IO.FileSystem.AccessControl.dll',
            'System.IO.FileSystem.dll',
            'System.IO.FileSystem.DriveInfo.dll',
            'System.IO.FileSystem.Primitives.dll',
            'System.IO.FileSystem.Watcher.dll',
            'System.IO.IsolatedStorage.dll',
            'System.IO.MemoryMappedFiles.dll',
            'System.IO.Pipes.AccessControl.dll',
            'System.IO.Pipes.dll',
            'System.IO.UnmanagedMemoryStream.dll',
            'System.Linq.dll',
            'System.Linq.Expressions.dll',
            'System.Linq.Parallel.dll',
            'System.Linq.Queryable.dll',
            'System.Memory.dll',
            'System.Net.dll',
            'System.Net.Http.dll',
            'System.Net.Http.Json.dll',
            'System.Net.HttpListener.dll',
            'System.Net.Mail.dll',
            'System.Net.NameResolution.dll',
            'System.Net.NetworkInformation.dll',
            'System.Net.Ping.dll',
            'System.Net.Primitives.dll',
            'System.Net.Requests.dll',
            'System.Net.Security.dll',
            'System.Net.ServicePoint.dll',
            'System.Net.Sockets.dll',
            'System.Net.WebClient.dll',
            'System.Net.WebHeaderCollection.dll',
            'System.Net.WebProxy.dll',
            'System.Net.WebSockets.Client.dll',
            'System.Net.WebSockets.dll',
            'System.Numerics.dll',
            'System.Numerics.Vectors.dll',
            'System.ObjectModel.dll',
            'System.Reflection.DispatchProxy.dll',
            'System.Reflection.dll',
            'System.Reflection.Emit.dll',
            'System.Reflection.Emit.ILGeneration.dll',
            'System.Reflection.Emit.Lightweight.dll',
            'System.Reflection.Extensions.dll',
            'System.Reflection.Metadata.dll',
            'System.Reflection.Primitives.dll',
            'System.Reflection.TypeExtensions.dll',
            'System.Resources.Reader.dll',
            'System.Resources.ResourceManager.dll',
            'System.Resources.Writer.dll',
            'System.Runtime.CompilerServices.Unsafe.dll',
            'System.Runtime.CompilerServices.VisualC.dll',
            'System.Runtime.Extensions.dll',
            'System.Runtime.Handles.dll',
            'System.Runtime.InteropServices.dll',
            'System.Runtime.InteropServices.RuntimeInformation.dll',
            'System.Runtime.Intrinsics.dll',
            'System.Runtime.Loader.dll',
            'System.Runtime.Numerics.dll',
            'System.Runtime.Serialization.dll',
            'System.Runtime.Serialization.Formatters.dll',
            'System.Runtime.Serialization.Json.dll',
            'System.Runtime.Serialization.Primitives.dll',
            'System.Runtime.Serialization.Xml.dll',
            'System.Security.AccessControl.dll',
            'System.Security.Claims.dll',
            'System.Security.Cryptography.Algorithms.dll',
            'System.Security.Cryptography.Cng.dll',
            'System.Security.Cryptography.Csp.dll',
            'System.Security.Cryptography.Encoding.dll',
            'System.Security.Cryptography.OpenSsl.dll',
            'System.Security.Cryptography.Primitives.dll',
            'System.Security.Cryptography.X509Certificates.dll',
            'System.Security.dll',
            'System.Security.Principal.dll',
            'System.Security.Principal.Windows.dll',
            'System.Security.SecureString.dll',
            'System.ServiceModel.Web.dll',
            'System.ServiceProcess.dll',
            'System.Text.Encoding.CodePages.dll',
            'System.Text.Encoding.dll',
            'System.Text.Encoding.Extensions.dll',
            'System.Text.Encodings.Web.dll',
            'System.Text.Json.dll',
            'System.Text.RegularExpressions.dll',
            'System.Threading.Channels.dll',
            'System.Threading.dll',
            'System.Threading.Overlapped.dll',
            'System.Threading.Tasks.Dataflow.dll',
            'System.Threading.Tasks.dll',
            'System.Threading.Tasks.Extensions.dll',
            'System.Threading.Tasks.Parallel.dll',
            'System.Threading.Thread.dll',
            'System.Threading.ThreadPool.dll',
            'System.Threading.Timer.dll',
            'System.Transactions.dll',
            'System.Transactions.Local.dll',
            'System.ValueTuple.dll',
            'System.Web.dll',
            'System.Web.HttpUtility.dll',
            'System.Windows.dll',
            'System.Xml.dll',
            'System.Xml.Linq.dll',
            'System.Xml.ReaderWriter.dll',
            'System.Xml.Serialization.dll',
            'System.Xml.XDocument.dll',
            'System.Xml.XmlDocument.dll',
            'System.Xml.XmlSerializer.dll',
            'System.Xml.XPath.dll',
            'System.Xml.XPath.XDocument.dll',
            'WindowsBase.dll',
        ]]
        return ['/nologo'] + default_refs

    def get_output_args(self, fname: str) -> T.List[str]:
        return self.get_always_args() + ['-out:' + fname, '/nullable:enable']

    def sanity_check(self, work_dir: str, environment: 'Environment') -> None:
        # Skip "is executable" sanity check since compiling executables with .NET Core csc is hard.
        src = 'sanity.cs'
        obj = 'sanity.exe'
        source_name = os.path.join(work_dir, src)
        with open(source_name, 'w', encoding='utf-8') as ofile:
            ofile.write(textwrap.dedent('''
                public class Sanity {
                    static public void Main () {
                    }
                }
                '''))
        pc = subprocess.Popen(self.exelist + self.get_always_args() + [src], cwd=work_dir)
        pc.wait()
        if pc.returncode != 0:
            raise EnvironmentException('C# compiler %s can not compile programs.' % self.name_string())

    def rsp_file_syntax(self) -> 'RSPFileSyntax':
        return RSPFileSyntax.MSVC
