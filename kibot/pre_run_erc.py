# -*- coding: utf-8 -*-
# Copyright (c) 2020-2024 Salvador E. Tropea
# Copyright (c) 2020-2024 Instituto Nacional de Tecnología Industrial
# License: AGPL-3.0
# Project: KiBot (formerly KiPlot)
"""
Dependencies:
  - from: KiAuto
    role: mandatory
    command: eeschema_do
    version: 2.2.1
"""
import os
from shutil import move
from .macros import macros, document, pre_class  # noqa: F401
from .gs import GS
from .optionable import Optionable
from .kiplot import load_sch
from .misc import ERC_ERROR, W_DEPR
from .log import get_logger

logger = get_logger(__name__)


class Run_ERCOptions(Optionable):
    """ ERC options """
    def __init__(self):
        super().__init__()
        with document:
            self.enabled = True
            """ Enable the ERC. This is the replacement for the boolean value """
            self.dir = ''
            """ Sub-directory for the report """
            self.warnings_as_errors = False
            """ ERC warnings are considered errors """
        self._unknown_is_error = True


@pre_class
class Run_ERC(BasePreFlight):  # noqa: F821
    def __init__(self):
        super().__init__()
        self._sch_related = True
        self._expand_id = 'erc'
        self._expand_ext = 'txt'
        with document:
            self.run_erc = Run_ERCOptions
            """ [boolean|dict=false] (Deprecated for KiCad 8, use *erc*) Runs the ERC (Electrical Rules Check).
                To ensure the schematic is electrically correct.
                The report file name is controlled by the global output pattern (%i=erc %x=txt) """

    def config(self, parent):
        super().config(parent)
        if isinstance(self.run_erc, bool):
            self._dir = ''
            self._warnings_as_errors = False
        else:  # Run_ERCOptions
            self._enabled = self.run_erc.enabled
            self._dir = self.run_erc.dir
            self._warnings_as_errors = self.run_erc.warnings_as_errors

    def get_targets(self):
        """ Returns a list of targets generated by this preflight """
        load_sch()
        out_pattern = GS.global_output if GS.global_output is not None else GS.def_global_output
        name = Optionable.expand_filename_sch(self, out_pattern)
        out_dir = self.expand_dirname(GS.out_dir)
        if GS.global_dir and GS.global_use_dir_for_preflights:
            out_dir = os.path.join(out_dir, self.expand_dirname(GS.global_dir))
        return [os.path.abspath(os.path.join(out_dir, self._dir, name))]

    def run(self):
        if GS.ki8:
            logger.warning(W_DEPR+'For KiCad 8 use the `erc` preflight instead of `run_erc`')
        command = self.ensure_tool('KiAuto')
        # Workaround for KiCad 7 odd behavior: it forces a file extension
        # Note: One thing is adding the extension before you enter a name, other is add something you removed on purpose
        tmp_name = GS.tmp_file(suffix='.rpt', prefix='erc_report', what='ERC report', a_logger=logger)
        cmd = [command, 'run_erc', '-o', os.path.basename(tmp_name), '-g', str(GS.global_erc_grid)]
        if self._warnings_as_errors or BasePreFlight.get_option('erc_warnings'):  # noqa: F821
            cmd.append('-w')
        if GS.filter_file:
            cmd.extend(['-f', GS.filter_file])
        cmd.extend([GS.sch_file, os.path.dirname(tmp_name)])
        # If we are in verbose mode enable debug in the child
        cmd = self.add_extra_options(cmd)
        logger.info('- Running the ERC')
        ret = self.exec_with_retry(cmd)
        # Move the report to the desired name
        output = self.get_targets()[0]
        os.makedirs(os.path.dirname(output), exist_ok=True)
        try:
            move(tmp_name, output)
        except FileNotFoundError:
            logger.error(' Oops!')
        if ret:
            if ret > 127:
                ret = -(256-ret)
            if ret < 0:
                msgs = [f'ERC errors: {-ret}']
            else:
                msgs = [f'ERC returned {ret}']
                if GS.sch.annotation_error:
                    msgs.append('Make sure your schematic is fully annotated')
            GS.exit_with_error(msgs, ERC_ERROR)
